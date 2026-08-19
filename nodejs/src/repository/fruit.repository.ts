import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';

import { Fruit } from '../domain/fruit.entity';
import { FRUIT_ROWS_SELECT, FruitRow, groupFruitRows } from './fruit-rows';
import { StoreCache } from './store.cache';

/**
 * Which read implementation to use, selected by the QUERY_MODE environment variable.
 *
 *  - `orm` (default) - TypeORM `find({ relations })`, the idiomatic implementation.
 *  - `sql`           - one hand-written join, no entity hydration. See fruit-rows.ts.
 *
 * Both produce identical JSON; only the read path differs. Read fresh on every call rather than
 * cached in a module-level constant: the cost is one env var lookup and string compare, which
 * does not show up next to an actual database round trip, and re-reading it is what lets
 * test/fruit.e2e-spec.ts exercise both modes in the same Jest process by setting
 * `process.env.QUERY_MODE` per describe block, with no module-cache tricks
 * (`jest.resetModules()`) needed. See README.md ("Two query implementations").
 */
export type FruitQueryMode = 'orm' | 'sql';

export function queryMode(): FruitQueryMode {
  return ((process.env.QUERY_MODE || 'orm').trim().toLowerCase() === 'sql') ? 'sql' : 'orm';
}

/**
 * Mirrors `org.acme.repository.FruitRepository` (a Panache `PanacheRepository<Fruit>`).
 *
 * In `orm` mode the read methods join `fruits` -> `store_fruit_prices` in one statement (`store`
 * deliberately left out of that join - see `StoreFruitPrice.store` in `store-fruit-price.entity.ts`)
 * and resolve each price's `store` from `StoreCache` instead of a relation. That is the
 * TypeORM-idiomatic counterpart of what the Java module does with a lazy `@OneToMany` plus an
 * EAGER `@ManyToOne` backed by Hibernate's second-level cache: the store lookups are served from
 * an in-process cache instead of hitting the database, without adding a second round trip to get
 * there. See README.md for why the query shapes differ even though the JSON responses are
 * identical.
 */
@Injectable()
export class FruitRepository {
  constructor(
    @InjectRepository(Fruit)
    private readonly repository: Repository<Fruit>,
    private readonly storeCache: StoreCache
  ) {}

  /** Panache `listAll()` - no ORDER BY, matching the Java implementation. */
  listAll(): Promise<Fruit[]> {
    return (queryMode() === 'sql') ? this.listAllSql() : this.listAllOrm();
  }

  /** Panache `find("name", name).firstResultOptional()`. */
  findByName(name: string): Promise<Fruit> {
    return (queryMode() === 'sql') ? this.findByNameSql(name) : this.findByNameOrm(name);
  }

  /**
   * Panache `persist()`. `fruits.id` has no DEFAULT in `scripts/dbdata/db.sql`, so the id is drawn
   * from the `fruits_seq` sequence first - exactly what Hibernate's `GenerationType.SEQUENCE` with
   * `allocationSize = 1` does. Unaffected by QUERY_MODE: writes are not benchmarked.
   */
  async persist(fruit: Fruit): Promise<Fruit> {
    return this.repository.manager.transaction(async (manager) => {
      const rows = await manager.query("SELECT nextval('fruits_seq')");
      fruit.id = Number(rows[0].nextval);

      await manager.insert(Fruit, fruit);

      return fruit;
    });
  }

  // --- orm mode (default) -------------------------------------------------------------------

  private async listAllOrm(): Promise<Fruit[]> {
    const fruits = await this.repository.find({
      relations: { storePrices: true }
    });

    await this.hydrateStores(fruits);

    return fruits;
  }

  private async findByNameOrm(name: string): Promise<Fruit> {
    const fruit = await this.repository.findOne({
      where: { name },
      relations: { storePrices: true }
    });

    if (fruit) {
      await this.hydrateStores([fruit]);
    }

    return fruit;
  }

  /**
   * Resolves every `storePrices[].store` from `StoreCache` in one bulk lookup, the TypeORM
   * counterpart of Hibernate serving the `store` association from its second-level cache. See
   * the class doc comment and `store.cache.ts`.
   */
  private async hydrateStores(fruits: Fruit[]): Promise<void> {
    const storeIds = fruits.flatMap((fruit) => fruit.storePrices.map((price) => price.storeId));
    const stores = await this.storeCache.getByIds(storeIds);

    for (const fruit of fruits) {
      for (const price of fruit.storePrices) {
        price.store = stores.get(price.storeId);
      }
    }
  }

  // --- sql mode ------------------------------------------------------------------------------

  private async listAllSql(): Promise<Fruit[]> {
    const rows: FruitRow[] = await this.repository.query(FRUIT_ROWS_SELECT);

    return groupFruitRows(rows);
  }

  private async findByNameSql(name: string): Promise<Fruit> {
    const rows: FruitRow[] = await this.repository.query(`${FRUIT_ROWS_SELECT} WHERE f.name = $1`, [name]);

    return groupFruitRows(rows)[0] ?? null;
  }
}

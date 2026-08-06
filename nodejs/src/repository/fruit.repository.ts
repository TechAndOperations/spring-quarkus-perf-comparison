import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';

import { Fruit } from '../domain/fruit.entity';
import { FRUIT_ROWS_SELECT, FruitRow, groupFruitRows } from './fruit-rows';

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
 * In `orm` mode the read methods eagerly join `storePrices` -> `store` in one statement, which is
 * the idiomatic TypeORM equivalent of what the Java module achieves with a lazy `@OneToMany` plus
 * an EAGER `@ManyToOne` backed by Hibernate's second-level cache. See README.md for why the query
 * shapes differ even though the JSON responses are identical.
 */
@Injectable()
export class FruitRepository {
  constructor(
    @InjectRepository(Fruit)
    private readonly repository: Repository<Fruit>
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

  private listAllOrm(): Promise<Fruit[]> {
    return this.repository.find({
      relations: { storePrices: { store: true } }
    });
  }

  private findByNameOrm(name: string): Promise<Fruit> {
    return this.repository.findOne({
      where: { name },
      relations: { storePrices: { store: true } }
    });
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

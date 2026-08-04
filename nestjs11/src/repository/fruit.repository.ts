import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';

import { Fruit } from '../domain/fruit.entity';

/**
 * Mirrors `org.acme.repository.FruitRepository` (a Panache `PanacheRepository<Fruit>`).
 *
 * The read methods eagerly join `storePrices` -> `store` in one statement, which is the idiomatic
 * TypeORM equivalent of what the Java module achieves with a lazy `@OneToMany` plus an EAGER
 * `@ManyToOne` backed by Hibernate's second-level cache. See README.md for why the query shapes
 * differ even though the JSON responses are identical.
 */
@Injectable()
export class FruitRepository {
  constructor(
    @InjectRepository(Fruit)
    private readonly repository: Repository<Fruit>
  ) {}

  /** Panache `listAll()` — no ORDER BY, matching the Java implementation. */
  listAll(): Promise<Fruit[]> {
    return this.repository.find({
      relations: { storePrices: { store: true } }
    });
  }

  /** Panache `find("name", name).firstResultOptional()`. */
  findByName(name: string): Promise<Fruit> {
    return this.repository.findOne({
      where: { name },
      relations: { storePrices: { store: true } }
    });
  }

  /**
   * Panache `persist()`. `fruits.id` has no DEFAULT in `scripts/dbdata/db.sql`, so the id is
   * drawn from the `fruits_seq` sequence first — exactly what Hibernate's
   * `GenerationType.SEQUENCE` with `allocationSize = 1` does.
   */
  async persist(fruit: Fruit): Promise<Fruit> {
    return this.repository.manager.transaction(async (manager) => {
      const rows = await manager.query("SELECT nextval('fruits_seq')");
      fruit.id = Number(rows[0].nextval);

      await manager.insert(Fruit, fruit);

      return fruit;
    });
  }
}

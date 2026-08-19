import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';

import { Store } from '../domain/store.entity';

/**
 * In-process analogue of Hibernate's second-level cache on `Store` (`@Cacheable` plus
 * `@Cache(NONSTRICT_READ_WRITE)` on the `store` association) in `quarkus3-virtual`'s
 * `Store`/`StoreFruitPrice` entities. TypeORM has no entity-level L2 cache, so this is a small
 * hand-rolled equivalent rather than a framework feature - see README.md ("Two query
 * implementations") for how it's used.
 *
 * No endpoint on any module writes a `Store`, so unlike Hibernate's cache there is no
 * invalidation path to build: once an id is resolved it stays correct for the process's
 * lifetime, matching how these entities actually behave at runtime.
 */
@Injectable()
export class StoreCache {
  private readonly byId = new Map<number, Store>();

  constructor(
    @InjectRepository(Store)
    private readonly repository: Repository<Store>
  ) {}

  /** Resolves every id from the cache, issuing one bulk query for whatever is missing. */
  async getByIds(ids: number[]): Promise<Map<number, Store>> {
    const misses = [...new Set(ids)].filter((id) => !this.byId.has(id));

    if (misses.length > 0) {
      const stores = await this.repository.find({ where: { id: In(misses) } });

      for (const store of stores) {
        this.byId.set(store.id, store);
      }
    }

    return this.byId;
  }
}

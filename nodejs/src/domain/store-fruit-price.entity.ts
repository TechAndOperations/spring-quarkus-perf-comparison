import { Column, Entity, JoinColumn, ManyToOne, PrimaryColumn } from 'typeorm';

import { Fruit } from './fruit.entity';
import { numericTransformer } from './numeric.transformer';
import { Store } from './store.entity';

/**
 * Mirrors `org.acme.domain.StoreFruitPrice`.
 *
 * The Java entity uses an `@EmbeddedId` (`StoreFruitPriceId`) with `@MapsId`. TypeORM has no
 * embedded-id equivalent, so the composite key is expressed as two `@PrimaryColumn`s whose
 * column names are reused by the relations — the standard TypeORM composite-key join-entity
 * pattern. The PK is `(fruit_id, store_id)` per `scripts/dbdata/db.sql`.
 *
 * `store` mirrors the Java entity's `@ManyToOne(FetchType.EAGER)` + `@Fetch(FetchMode.SELECT)` +
 * `@Cache(NONSTRICT_READ_WRITE)`: always populated, but via a cached lookup rather than a join or
 * a per-row query. Marking it `eager: true` here would make TypeORM add it back into every join;
 * instead `FruitRepository.hydrateStores()` populates it from `StoreCache` after loading, using
 * `storeId` (already selected as part of the primary key, no relation load needed to get it).
 * `store` is `undefined` on any `StoreFruitPrice` loaded outside that path. `fruit` stays LAZY,
 * matching the Java entity - nothing in this API ever reads it.
 */
@Entity('store_fruit_prices')
export class StoreFruitPrice {
  @PrimaryColumn({ name: 'fruit_id', type: 'bigint', transformer: numericTransformer })
  fruitId: number;

  @PrimaryColumn({ name: 'store_id', type: 'bigint', transformer: numericTransformer })
  storeId: number;

  @ManyToOne(() => Store, { nullable: false })
  @JoinColumn({ name: 'store_id', referencedColumnName: 'id' })
  store: Store;

  @ManyToOne(() => Fruit, (fruit) => fruit.storePrices, { lazy: true, nullable: false })
  @JoinColumn({ name: 'fruit_id', referencedColumnName: 'id' })
  fruit: Promise<Fruit>;

  @Column({ type: 'numeric', precision: 12, scale: 2, nullable: false, transformer: numericTransformer })
  price: number;
}

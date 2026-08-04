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
 * Fetch strategies match the Java entity: `store` is EAGER, `fruit` is LAZY.
 */
@Entity('store_fruit_prices')
export class StoreFruitPrice {
  @PrimaryColumn({ name: 'fruit_id', type: 'bigint', transformer: numericTransformer })
  fruitId: number;

  @PrimaryColumn({ name: 'store_id', type: 'bigint', transformer: numericTransformer })
  storeId: number;

  @ManyToOne(() => Store, { eager: true, nullable: false })
  @JoinColumn({ name: 'store_id', referencedColumnName: 'id' })
  store: Store;

  @ManyToOne(() => Fruit, (fruit) => fruit.storePrices, { lazy: true, nullable: false })
  @JoinColumn({ name: 'fruit_id', referencedColumnName: 'id' })
  fruit: Promise<Fruit>;

  @Column({ type: 'numeric', precision: 12, scale: 2, nullable: false, transformer: numericTransformer })
  price: number;
}

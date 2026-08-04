import { Column, Entity, OneToMany, PrimaryColumn } from 'typeorm';

import { numericTransformer } from './numeric.transformer';
import { StoreFruitPrice } from './store-fruit-price.entity';

/**
 * Mirrors `org.acme.domain.Fruit`.
 *
 * `id` comes from the `fruits_seq` sequence (see {@link Store} for why it is not generated
 * by the column itself). `storePrices` is the inverse side of the relationship and is not
 * a column, matching `@OneToMany(mappedBy = "fruit")`.
 */
@Entity('fruits')
export class Fruit {
  @PrimaryColumn({ type: 'bigint', transformer: numericTransformer })
  id: number;

  @Column({ nullable: false, unique: true })
  name: string;

  @Column({ nullable: true })
  description: string;

  @OneToMany(() => StoreFruitPrice, (storeFruitPrice) => storeFruitPrice.fruit)
  storePrices: StoreFruitPrice[];
}

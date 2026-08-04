import { Column, Entity, PrimaryColumn } from 'typeorm';

import { Address } from './address.entity';
import { numericTransformer } from './numeric.transformer';

/**
 * Mirrors `org.acme.domain.Store`.
 *
 * `id` is populated from the `stores_seq` sequence rather than an identity column, matching
 * Hibernate's `GenerationType.SEQUENCE` — the `stores.id` column has no DEFAULT in
 * `scripts/dbdata/db.sql`, so it must always be supplied by the application.
 */
@Entity('stores')
export class Store {
  @PrimaryColumn({ type: 'bigint', transformer: numericTransformer })
  id: number;

  @Column({ nullable: false, unique: true })
  name: string;

  @Column({ nullable: false })
  currency: string;

  @Column(() => Address, { prefix: false })
  address: Address;
}

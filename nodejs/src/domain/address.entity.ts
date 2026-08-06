import { Column } from 'typeorm';

/**
 * Mirrors the `@Embeddable` record `org.acme.domain.Address`.
 *
 * Embedded into {@link Store} with `prefix: false` so the columns stay flat and bare
 * (`address`, `city`, `country`) as declared in `scripts/dbdata/db.sql`. TypeORM would
 * otherwise prefix them with the owning property name (`addressAddress`, ...).
 */
export class Address {
  @Column({ nullable: false })
  address: string;

  @Column({ nullable: false })
  city: string;

  @Column({ nullable: false })
  country: string;
}

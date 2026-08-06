import { IsNotEmpty, IsOptional } from 'class-validator';

import { StoreFruitPriceDTO } from './store-fruit-price.dto';

/**
 * Mirrors the `org.acme.dto.FruitDTO` record. JSON key order: id, name, description, storePrices.
 *
 * Only `name` is validated, matching the Java record's single `@NotBlank`. Nested validation is
 * deliberately not cascaded into `storePrices` — the Java DTO has no `@Valid` on that field.
 */
export class FruitDTO {
  @IsOptional()
  id?: number;

  @IsNotEmpty({ message: 'Name is mandatory' })
  name: string;

  @IsOptional()
  description?: string;

  @IsOptional()
  storePrices?: StoreFruitPriceDTO[];
}

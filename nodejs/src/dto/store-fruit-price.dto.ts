import { IsOptional, Min } from 'class-validator';

import { StoreDTO } from './store.dto';

/** Mirrors the `org.acme.dto.StoreFruitPriceDTO` record. JSON key order: store, price. */
export class StoreFruitPriceDTO {
  @IsOptional()
  store?: StoreDTO;

  @Min(0, { message: 'Price must be >= 0' })
  price: number;
}

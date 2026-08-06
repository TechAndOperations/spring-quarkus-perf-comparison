import { StoreFruitPrice } from '../domain/store-fruit-price.entity';
import { StoreFruitPriceDTO } from '../dto/store-fruit-price.dto';
import { storeToDto } from './store.mapper';

/**
 * Mirrors `org.acme.mapping.StoreFruitPriceMapper`.
 *
 * Entity -> DTO only. The Java mapper has no reverse direction because prices are never created
 * through this API, so nothing is added here either.
 */
export function storeFruitPriceToDto(storeFruitPrice: StoreFruitPrice): StoreFruitPriceDTO {
  if (storeFruitPrice === null || storeFruitPrice === undefined) {
    return null;
  }

  // Keys inserted in record-declaration order: store, price.
  const dto = {} as StoreFruitPriceDTO;

  const store = storeToDto(storeFruitPrice.store);

  if (store !== null) {
    dto.store = store;
  }

  // Jackson's NON_EMPTY inclusion keeps numbers (including 0), so only null/undefined is dropped.
  if (storeFruitPrice.price !== null && storeFruitPrice.price !== undefined) {
    dto.price = storeFruitPrice.price;
  }

  return dto;
}

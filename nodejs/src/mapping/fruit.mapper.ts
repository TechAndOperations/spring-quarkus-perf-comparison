import { Fruit } from '../domain/fruit.entity';
import { FruitDTO } from '../dto/fruit.dto';
import { storeFruitPriceToDto } from './store-fruit-price.mapper';

/**
 * Mirrors `org.acme.mapping.FruitMapper`.
 *
 * Empty/null fields are omitted to replicate the Java module's Jackson setting
 * `quarkus.jackson.serialization-inclusion: non-empty` (see
 * `quarkus3-virtual/src/main/resources/application.yml`). `JSON.stringify` would otherwise emit
 * `"description":null` / `"storePrices":[]` where the Java implementation emits nothing.
 */
export function fruitToDto(fruit: Fruit): FruitDTO {
  if (fruit === null || fruit === undefined) {
    return null;
  }

  const prices = fruit.storePrices
    ? fruit.storePrices.map(storeFruitPriceToDto).filter((price) => price !== null)
    : null;

  // Keys inserted in record-declaration order: id, name, description, storePrices.
  const dto = {} as FruitDTO;

  if (fruit.id !== null && fruit.id !== undefined) {
    dto.id = fruit.id;
  }

  if (fruit.name) {
    dto.name = fruit.name;
  }

  if (fruit.description) {
    dto.description = fruit.description;
  }

  if (prices !== null && prices.length > 0) {
    dto.storePrices = prices;
  }

  return dto;
}

/**
 * Deliberately maps only `name` and `description`, exactly like the Java mapper, whose comment
 * reads "The rest of the relationships aren't built out yet". Do not "fix" this without also
 * changing `quarkus3-virtual` — module parity is the point of this repo.
 */
export function fruitFromDto(fruitDTO: FruitDTO): Fruit {
  if (fruitDTO === null || fruitDTO === undefined) {
    return null;
  }

  const fruit = new Fruit();
  fruit.name = fruitDTO.name;
  fruit.description = fruitDTO.description;

  return fruit;
}

import { Address } from '../domain/address.entity';
import { Fruit } from '../domain/fruit.entity';
import { Store } from '../domain/store.entity';
import { StoreFruitPrice } from '../domain/store-fruit-price.entity';
import { FruitDTO } from '../dto/fruit.dto';
import { fruitFromDto, fruitToDto } from './fruit.mapper';

function address(): Address {
  const value = new Address();
  value.address = '123 Main St';
  value.city = 'Anytown';
  value.country = 'USA';

  return value;
}

function store(): Store {
  const value = new Store();
  value.id = 1;
  value.name = 'Store 1';
  value.currency = 'USD';
  value.address = address();

  return value;
}

function price(amount: number): StoreFruitPrice {
  const value = new StoreFruitPrice();
  value.fruitId = 1;
  value.storeId = 1;
  value.store = store();
  value.price = amount;

  return value;
}

function apple(): Fruit {
  const value = new Fruit();
  value.id = 1;
  value.name = 'Apple';
  value.description = 'Hearty fruit';
  value.storePrices = [price(1.29)];

  return value;
}

describe('fruitToDto', () => {
  it('maps a fruit with its nested store prices', () => {
    expect(fruitToDto(apple())).toEqual({
      id: 1,
      name: 'Apple',
      description: 'Hearty fruit',
      storePrices: [
        {
          store: { id: 1, name: 'Store 1', currency: 'USD', address: { address: '123 Main St', city: 'Anytown', country: 'USA' } },
          price: 1.29
        }
      ]
    });
  });

  it('serialises ids and prices as JSON numbers, not strings', () => {
    // node-postgres hands back bigint/numeric as strings; the entity transformers coerce them so
    // the JSON matches the Java modules. Guard against a regression in numeric.transformer.ts.
    const json = JSON.stringify(fruitToDto(apple()));

    expect(json).toContain('"id":1');
    expect(json).toContain('"price":1.29');
    expect(json).not.toContain('"id":"1"');
    expect(json).not.toContain('"price":"1.29"');
  });

  it('emits keys in the same order as the Java record', () => {
    expect(Object.keys(fruitToDto(apple()))).toEqual(['id', 'name', 'description', 'storePrices']);
  });

  it('omits null and empty fields, replicating Jackson NON_EMPTY inclusion', () => {
    const fruit = new Fruit();
    fruit.id = 11;
    fruit.name = 'Grapefruit';
    fruit.description = null;
    fruit.storePrices = [];

    const dto = fruitToDto(fruit);

    expect(dto).toEqual({ id: 11, name: 'Grapefruit' });
    expect(JSON.stringify(dto)).toBe('{"id":11,"name":"Grapefruit"}');
  });

  it('keeps a zero price, which is not "empty" for Jackson', () => {
    const fruit = apple();
    fruit.storePrices = [price(0)];

    expect(fruitToDto(fruit).storePrices[0].price).toBe(0);
  });

  it('drops null entries from storePrices', () => {
    const fruit = apple();
    fruit.storePrices = [null, price(1.29)];

    expect(fruitToDto(fruit).storePrices).toHaveLength(1);
  });

  it('returns null for a null fruit', () => {
    expect(fruitToDto(null)).toBeNull();
  });
});

describe('fruitFromDto', () => {
  it('maps only name and description, matching the Java mapper', () => {
    // The Java FruitMapper deliberately leaves id and storePrices unmapped ("The rest of the
    // relationships aren't built out yet"). Changing this would break parity with quarkus3-virtual.
    const dto: FruitDTO = {
      id: 99,
      name: 'Grapefruit',
      description: 'Summer fruit',
      storePrices: [{ store: { name: 'Store 1', currency: 'USD' }, price: 1.5 }]
    };

    const fruit = fruitFromDto(dto);

    expect(fruit.name).toBe('Grapefruit');
    expect(fruit.description).toBe('Summer fruit');
    expect(fruit.id).toBeUndefined();
    expect(fruit.storePrices).toBeUndefined();
  });

  it('returns null for a null DTO', () => {
    expect(fruitFromDto(null)).toBeNull();
  });
});

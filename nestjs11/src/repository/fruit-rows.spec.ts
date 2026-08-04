import { fruitToDto } from '../mapping/fruit.mapper';
import { FruitRow, groupFruitRows } from './fruit-rows';

function row(over: Partial<FruitRow>): FruitRow {
  return {
    f_id: '1', f_name: 'Apple', f_description: 'Hearty fruit',
    p_price: '1.29',
    s_id: '1', s_name: 'Store 1', s_currency: 'USD',
    s_address: '123 Main St', s_city: 'Anytown', s_country: 'USA',
    ...over
  } as FruitRow;
}

describe('groupFruitRows', () => {
  it('collapses several join rows into one fruit', () => {
    const fruits = groupFruitRows([
      row({}),
      row({ p_price: '2.49', s_id: '2', s_name: 'Store 2', s_currency: 'EUR', s_address: '456 Main St', s_city: 'Paris', s_country: 'France' })
    ]);

    expect(fruits).toHaveLength(1);
    expect(fruits[0].storePrices).toHaveLength(2);
  });

  it('coerces bigint and numeric strings into JS numbers', () => {
    // Raw queries bypass the entity value transformers, so this coercion is what keeps the API
    // emitting {"id":1,"price":1.29} rather than {"id":"1","price":"1.29"}.
    const [fruit] = groupFruitRows([row({})]);

    expect(fruit.id).toBe(1);
    expect(typeof fruit.id).toBe('number');
    expect(fruit.storePrices[0].price).toBe(1.29);
    expect(typeof fruit.storePrices[0].price).toBe('number');
    expect(fruit.storePrices[0].store.id).toBe(1);
  });

  it('handles a fruit with no prices (LEFT JOIN nulls)', () => {
    const [fruit] = groupFruitRows([
      row({ f_id: '11', f_name: 'Grapefruit', f_description: 'Summer fruit',
            p_price: null, s_id: null, s_name: null, s_currency: null,
            s_address: null, s_city: null, s_country: null } as Partial<FruitRow>)
    ]);

    expect(fruit.storePrices).toEqual([]);
    // Jackson NON_EMPTY parity: an empty collection must disappear from the JSON.
    expect(JSON.stringify(fruitToDto(fruit))).toBe('{"id":11,"name":"Grapefruit","description":"Summer fruit"}');
  });

  it('keeps several distinct fruits in first-appearance order', () => {
    const fruits = groupFruitRows([
      row({ f_id: '1', f_name: 'Apple' }),
      row({ f_id: '2', f_name: 'Pear' }),
      row({ f_id: '1', f_name: 'Apple', p_price: '0.99' })
    ]);

    expect(fruits.map((f) => f.name)).toEqual(['Apple', 'Pear']);
    expect(fruits[0].storePrices).toHaveLength(2);
  });

  it('produces exactly the same DTO as the ORM path would', () => {
    // The ORM path yields entity instances; this path yields plain objects. Both go through
    // fruitToDto, so the serialised result must be indistinguishable.
    const [fromSql] = groupFruitRows([row({})]);

    expect(JSON.stringify(fruitToDto(fromSql))).toBe(JSON.stringify(fruitToDto({
      id: 1, name: 'Apple', description: 'Hearty fruit',
      storePrices: [{
        store: { id: 1, name: 'Store 1', currency: 'USD',
                 address: { address: '123 Main St', city: 'Anytown', country: 'USA' } },
        price: 1.29
      }]
    } as any)));
  });
});

import { Fruit } from '../domain/fruit.entity';

/**
 * Single-statement alternative to TypeORM's `find({ relations })`, used when
 * FRUITS_QUERY_MODE=sql. See README.md ("Two query implementations").
 *
 * The ORM path builds ~250 entity instances per GET /fruits (11 fruits, 34 prices, their stores),
 * running a value transformer per column and installing prototype accessors for the lazy `fruit`
 * relation that nothing ever reads. This path skips all of that and assembles plain objects, then
 * hands them to the existing mappers so the JSON output stays byte-identical.
 *
 * No ORDER BY, matching both the ORM path and the Java implementation's `listAll()`.
 */
export const FRUIT_ROWS_SELECT = `
  SELECT f.id          AS f_id,
         f.name        AS f_name,
         f.description AS f_description,
         p.price       AS p_price,
         s.id          AS s_id,
         s.name        AS s_name,
         s.currency    AS s_currency,
         s.address     AS s_address,
         s.city        AS s_city,
         s.country     AS s_country
    FROM fruits f
    LEFT JOIN store_fruit_prices p ON p.fruit_id = f.id
    LEFT JOIN stores s             ON s.id = p.store_id`;

export interface FruitRow {
  f_id: string;
  f_name: string;
  f_description: string;
  p_price: string;
  s_id: string;
  s_name: string;
  s_currency: string;
  s_address: string;
  s_city: string;
  s_country: string;
}

/**
 * Collapses the flat join result into fruit-shaped objects.
 *
 * Raw queries bypass the entity value transformers, so `bigint` and `numeric` arrive as strings
 * here and must be coerced explicitly - otherwise the API would emit `"id":"1"` / `"price":"1.29"`
 * where every other module emits numbers.
 *
 * Fruit order follows first appearance in the result set, so it matches whatever Postgres returned.
 */
export function groupFruitRows(rows: FruitRow[]): Fruit[] {
  const byId = new Map<string, Fruit>();

  for (const row of rows) {
    let fruit = byId.get(row.f_id);

    if (!fruit) {
      // Plain object rather than a Fruit instance: the mappers only read properties, and skipping
      // entity construction is the point of this path.
      fruit = {
        id: Number(row.f_id),
        name: row.f_name,
        description: row.f_description,
        storePrices: []
      } as unknown as Fruit;

      byId.set(row.f_id, fruit);
    }

    // LEFT JOIN: a fruit with no prices yields one row with every p_/s_ column null.
    if (row.p_price !== null && row.p_price !== undefined) {
      fruit.storePrices.push({
        store: {
          id: Number(row.s_id),
          name: row.s_name,
          currency: row.s_currency,
          address: { address: row.s_address, city: row.s_city, country: row.s_country }
        },
        price: Number(row.p_price)
      } as any);
    }
  }

  return [...byId.values()];
}

import { ValueTransformer } from 'typeorm';

/**
 * node-postgres returns `bigint` (OID 20) and `numeric` (OID 1700) as strings to avoid
 * precision loss. The Java implementation exposes them as `Long` / `BigDecimal`, which
 * Jackson serialises as JSON numbers, so we coerce on read to keep the API byte-identical
 * across modules (`{"id":1,"price":1.29}`, not `{"id":"1","price":"1.29"}`).
 */
export const numericTransformer: ValueTransformer = {
  to: (value: number): number => value,
  from: (value: string): number => ((value === null || value === undefined) ? null : Number(value))
};

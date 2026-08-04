import { IsNotEmpty, IsOptional } from 'class-validator';

import { AddressDTO } from './address.dto';

/** Mirrors the `org.acme.dto.StoreDTO` record. JSON key order: id, name, currency, address. */
export class StoreDTO {
  @IsOptional()
  id?: number;

  @IsNotEmpty({ message: 'Name is mandatory' })
  name: string;

  @IsNotEmpty({ message: 'Currency is mandatory' })
  currency: string;

  @IsOptional()
  address?: AddressDTO;
}

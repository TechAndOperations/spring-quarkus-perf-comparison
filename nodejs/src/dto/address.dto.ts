import { IsNotEmpty } from 'class-validator';

/** Mirrors the `org.acme.dto.AddressDTO` record. JSON key order: address, city, country. */
export class AddressDTO {
  @IsNotEmpty({ message: 'Address is mandatory' })
  address: string;

  @IsNotEmpty({ message: 'City is mandatory' })
  city: string;

  @IsNotEmpty({ message: 'Country is mandatory' })
  country: string;
}

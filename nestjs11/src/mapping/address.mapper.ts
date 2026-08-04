import { Address } from '../domain/address.entity';
import { AddressDTO } from '../dto/address.dto';

/**
 * Mirrors `org.acme.mapping.AddressMapper` — hand-written, no mapping library, matching the
 * Java module's `final class` + static `map()` style.
 */
export function addressToDto(address: Address): AddressDTO {
  if (address === null || address === undefined) {
    return null;
  }

  // Keys inserted in record-declaration order so the JSON matches the Java output exactly.
  const dto = {} as AddressDTO;

  if (address.address) {
    dto.address = address.address;
  }

  if (address.city) {
    dto.city = address.city;
  }

  if (address.country) {
    dto.country = address.country;
  }

  return dto;
}

export function addressFromDto(addressDTO: AddressDTO): Address {
  if (addressDTO === null || addressDTO === undefined) {
    return null;
  }

  const address = new Address();
  address.address = addressDTO.address;
  address.city = addressDTO.city;
  address.country = addressDTO.country;

  return address;
}

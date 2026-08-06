import { Store } from '../domain/store.entity';
import { StoreDTO } from '../dto/store.dto';
import { addressFromDto, addressToDto } from './address.mapper';

/** Mirrors `org.acme.mapping.StoreMapper`. */
export function storeToDto(store: Store): StoreDTO {
  if (store === null || store === undefined) {
    return null;
  }

  // Keys inserted in record-declaration order: id, name, currency, address.
  const dto = {} as StoreDTO;

  if (store.id !== null && store.id !== undefined) {
    dto.id = store.id;
  }

  if (store.name) {
    dto.name = store.name;
  }

  if (store.currency) {
    dto.currency = store.currency;
  }

  const address = addressToDto(store.address);

  if (address !== null) {
    dto.address = address;
  }

  return dto;
}

/** The Java mapper always maps the DTO -> entity direction with a null id. */
export function storeFromDto(storeDTO: StoreDTO): Store {
  if (storeDTO === null || storeDTO === undefined) {
    return null;
  }

  const store = new Store();
  store.id = null;
  store.name = storeDTO.name;
  store.currency = storeDTO.currency;
  store.address = addressFromDto(storeDTO.address);

  return store;
}

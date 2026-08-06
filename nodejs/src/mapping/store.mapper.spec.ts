import { Address } from '../domain/address.entity';
import { Store } from '../domain/store.entity';
import { addressToDto } from './address.mapper';
import { storeFromDto, storeToDto } from './store.mapper';

describe('addressToDto', () => {
  it('maps all three fields', () => {
    const address = new Address();
    address.address = '456 Main St';
    address.city = 'Paris';
    address.country = 'France';

    expect(addressToDto(address)).toEqual({ address: '456 Main St', city: 'Paris', country: 'France' });
    expect(Object.keys(addressToDto(address))).toEqual(['address', 'city', 'country']);
  });

  it('returns null for a null address', () => {
    expect(addressToDto(null)).toBeNull();
  });
});

describe('storeToDto', () => {
  it('emits keys in the same order as the Java record', () => {
    const store = new Store();
    store.id = 2;
    store.name = 'Store 2';
    store.currency = 'EUR';
    store.address = null;

    expect(Object.keys(storeToDto(store))).toEqual(['id', 'name', 'currency']);
  });

  it('returns null for a null store', () => {
    expect(storeToDto(null)).toBeNull();
  });
});

describe('storeFromDto', () => {
  it('always maps a null id, matching the Java mapper', () => {
    const store = storeFromDto({ id: 7, name: 'Store 7', currency: 'EUR' });

    expect(store.id).toBeNull();
    expect(store.name).toBe('Store 7');
    expect(store.currency).toBe('EUR');
  });
});

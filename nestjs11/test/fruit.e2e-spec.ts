import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';

import { AppModule } from '../src/app.module';

/**
 * Mirrors `quarkus3-virtual`'s `FruitControllerEndToEndTest`: hits the real endpoints against the
 * real database, seeded by `scripts/dbdata/db.sql`.
 *
 * Requires the shared Postgres container to be up (`cd scripts && ./infra.sh -s`). OpenTelemetry
 * is disabled here so the suite does not need the LGTM collector.
 */
describe('FruitController (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    process.env.OTEL_SDK_DISABLED = 'true';

    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();

    app = moduleRef.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ transform: true }));
    await app.init();
  });

  afterAll(async () => {
    await app?.close();
  });

  it('GET /fruits returns the seeded fruits with nested store prices', async () => {
    const response = await request(app.getHttpServer()).get('/fruits').expect(200);

    expect(response.body.length).toBeGreaterThanOrEqual(10);

    // Assert on a known fruit rather than a fixed index: neither this module nor the Java one
    // applies an ORDER BY, so row order is whatever Postgres returns.
    const apple = response.body.find((fruit) => fruit.name === 'Apple');

    expect(apple).toBeDefined();
    expect(apple.id).toBe(1);
    expect(apple.description).toBe('Hearty fruit');
    expect(apple.storePrices.length).toBeGreaterThan(0);

    const storePrice = apple.storePrices.find((price) => price.store.name === 'Store 1');

    expect(storePrice.price).toBe(1.29);
    expect(typeof storePrice.price).toBe('number');
    expect(storePrice.store.currency).toBe('USD');
    expect(storePrice.store.address).toEqual({ address: '123 Main St', city: 'Anytown', country: 'USA' });
  });

  it('GET /fruits/{name} returns the fruit', async () => {
    const response = await request(app.getHttpServer()).get('/fruits/Apple').expect(200);

    expect(response.body.name).toBe('Apple');
    expect(response.body.description).toBe('Hearty fruit');
  });

  it('GET /fruits/{name} returns 404 with an empty body when not found', async () => {
    const response = await request(app.getHttpServer()).get('/fruits/NotAFruit').expect(404);

    // The JAX-RS implementation returns a bare 404. NestJS's NotFoundException would have
    // produced a {"statusCode":404,...} body here.
    expect(response.text).toBe('');
  });

  it('POST /fruits creates a fruit and returns 200', async () => {
    const name = `Grapefruit-${Date.now()}`;

    const response = await request(app.getHttpServer())
      .post('/fruits')
      .send({ name, description: 'Summer fruit' })
      .expect(200);

    expect(response.body.name).toBe(name);
    expect(response.body.description).toBe('Summer fruit');
    expect(response.body.id).toBeGreaterThan(10);
    // storePrices is unset on create (see fruitFromDto) and omitted when empty.
    expect(response.body.storePrices).toBeUndefined();

    await request(app.getHttpServer()).get(`/fruits/${name}`).expect(200);
  });

  it('POST /fruits rejects a blank name', async () => {
    await request(app.getHttpServer()).post('/fruits').send({ description: 'No name' }).expect(400);
  });
});

import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';

import { AppModule } from '../src/app.module';

/**
 * Mirrors `quarkus3-virtual`'s `FruitControllerEndToEndTest` and the Rust/Go modules'
 * equivalents (`rust/tests/fruit_test.rs`, `go/integration_test.go`): hits the real endpoints
 * against the real database, seeded by `scripts/dbdata/db.sql`.
 *
 * Requires the shared Postgres container to be up (`cd scripts && ./infra.sh -s`). OpenTelemetry
 * is disabled here so the suite does not need the LGTM collector.
 *
 * Every describe block below runs against both QUERY_MODE values ("orm" and "sql") - the same
 * approach taken in `rust/`/`go/` (dual-mode test loop), adopted here because this module is
 * where the comparison was originally checked only by hand and produced a wrong first read of
 * the speedup - see README.md ("Two query implementations") for that history.
 *
 * This only works cleanly because `FruitRepository` reads `process.env.QUERY_MODE` fresh on
 * every call (see `src/repository/fruit.repository.ts::queryMode()`) rather than caching it in a
 * module-level constant - setting the env var per describe block is enough, no
 * `jest.resetModules()`/module-cache tricks needed.
 */
for (const mode of ['orm', 'sql']) {
  describe(`FruitController (e2e, QUERY_MODE=${mode})`, () => {
    let app: INestApplication;

    beforeAll(async () => {
      process.env.OTEL_SDK_DISABLED = 'true';
      process.env.QUERY_MODE = mode;

      const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();

      app = moduleRef.createNestApplication();
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
      const name = `Grapefruit-${mode}-${Date.now()}`;

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
}

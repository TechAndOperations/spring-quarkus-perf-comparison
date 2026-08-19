import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';

import { Fruit } from './domain/fruit.entity';
import { Store } from './domain/store.entity';
import { StoreFruitPrice } from './domain/store-fruit-price.entity';
import { HealthController } from './health/health.controller';
import { FruitRepository } from './repository/fruit.repository';
import { StoreCache } from './repository/store.cache';
import { FruitController } from './rest/fruit.controller';
import { FruitService } from './service/fruit.service';

@Module({
  imports: [
    TypeOrmModule.forRoot({
      type: 'postgres',
      // Every sibling module hardcodes localhost:5432 (see quarkus3-virtual application.yml,
      // "%prod" profile) because infra.sh publishes the container port on the benchmark host.
      // Override with DB_HOST when running against a database elsewhere.
      host: process.env.DB_HOST || 'localhost',
      port: Number(process.env.DB_PORT || 5432),
      username: process.env.DB_USER || 'fruits',
      password: process.env.DB_PASSWORD || 'fruits',
      database: process.env.DB_NAME || 'fruits',
      entities: [Fruit, Store, StoreFruitPrice],
      // The schema is owned by scripts/dbdata/db.sql and shared with every other module.
      // TypeORM must never create or alter it.
      synchronize: false,
      logging: false,
      // Agroal's default maximum pool size in the Quarkus modules is 20.
      extra: { max: Number(process.env.DB_POOL_MAX || 20) }
    }),
    TypeOrmModule.forFeature([Fruit, Store, StoreFruitPrice])
  ],
  controllers: [FruitController, HealthController],
  providers: [FruitService, FruitRepository, StoreCache]
})
export class AppModule {}

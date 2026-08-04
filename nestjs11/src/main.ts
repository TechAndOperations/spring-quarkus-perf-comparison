// Must be the first import so the OpenTelemetry auto-instrumentations can patch http/pg/nest
// before those modules are loaded.
import './tracing';
import 'reflect-metadata';

import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';

import { AppModule } from './app.module';

const PORT = Number(process.env.PORT || 8080);

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule, { logger: false });

  app.useGlobalPipes(new ValidationPipe({ transform: true }));

  await app.listen(PORT, '0.0.0.0');

  // `performance.now()` is milliseconds since process start, so this is the whole startup cost.
  // The wording mirrors Quarkus/Spring so the pipeline's logFileStartedRegex
  // (".*nestjs11.+started in.*") can detect readiness — see scripts/perf-lab/main.yml watch-log.
  const startedIn = (performance.now() / 1000).toFixed(3);
  console.log(`nestjs11 1.0 on Node ${process.version} (powered by NestJS) started in ${startedIn}s. Listening on: http://0.0.0.0:${PORT}`);
}

bootstrap();

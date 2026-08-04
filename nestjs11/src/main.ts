// Must be the very first import: the V8 compile cache only covers modules loaded after it is
// enabled, and CommonJS evaluates requires in order.
import './compile-cache';
// Second, so the OpenTelemetry auto-instrumentations can patch http/pg/nest before those modules
// are loaded.
import './tracing';
import 'reflect-metadata';

import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';

import { AppModule } from './app.module';
import { FRUIT_QUERY_MODE } from './repository/fruit.repository';

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

  // Logged on its own line, after the readiness line, so the benchmark log records which read
  // implementation produced the numbers. Keep it off the readiness line to avoid disturbing the
  // pipeline's startup regex.
  console.log(`nestjs11 configuration: query mode=${FRUIT_QUERY_MODE}, compile cache=${process.env.NODE_COMPILE_CACHE_DISABLED === 'true' ? 'off' : 'on'}, otel=${process.env.OTEL_SDK_DISABLED === 'true' ? 'off' : 'on'}`);
}

bootstrap();

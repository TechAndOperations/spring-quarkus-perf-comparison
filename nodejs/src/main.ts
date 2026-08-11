// Must be the very first import: the V8 compile cache only covers modules loaded after it is
// enabled, and CommonJS evaluates requires in order.
import './compile-cache';
// Second, so the OpenTelemetry auto-instrumentations can patch http/pg/nest before those modules
// are loaded.
import './tracing';
import 'reflect-metadata';

import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { logs, SeverityNumber } from '@opentelemetry/api-logs';

import { AppModule } from './app.module';
import { queryMode } from './repository/fruit.repository';

const PORT = Number(process.env.PORT || 8080);

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule, { logger: false });

  app.useGlobalPipes(new ValidationPipe({ transform: true }));

  await app.listen(PORT, '0.0.0.0');

  // `performance.now()` is milliseconds since process start, so this is the whole startup cost.
  // The wording mirrors Quarkus/Spring so the pipeline's logFileStartedRegex
  // (".*nodejs.+started in.*") can detect readiness — see scripts/perf-lab/main.yml watch-log.
  const startedIn = (performance.now() / 1000).toFixed(3);
  console.log(`nodejs 1.0 on Node ${process.version} (powered by NestJS) started in ${startedIn}s. Listening on: http://0.0.0.0:${PORT}`);

  // Logged on its own line, after the readiness line, so the benchmark log records which read
  // implementation produced the numbers. Keep it off the readiness line to avoid disturbing the
  // pipeline's startup regex.
  const configuration = `nodejs configuration: query mode=${queryMode()}, compile cache=${process.env.NODE_COMPILE_CACHE_DISABLED === 'true' ? 'off' : 'on'}, otel=${process.env.OTEL_SDK_DISABLED === 'true' ? 'off' : 'on'}`;
  console.log(configuration);

  // Same line through the logs API, so the third signal carries something: NestJS runs with
  // `logger: false` and everything else here is console.log, which no instrumentation picks up -
  // without this the exporter stays idle and the service never appears in Loki. Emitted on top of
  // the console write, not instead of it: the benchmark's app log is the only place a failing
  // exporter is visible. No-op when OTEL_SDK_DISABLED leaves the global provider unset.
  logs.getLogger('nodejs').emit({
    severityNumber: SeverityNumber.INFO,
    severityText: 'INFO',
    body: configuration
  });
}

bootstrap();

import { Controller, Get } from '@nestjs/common';

/**
 * Minimal stand-in for the `quarkus-smallrye-health` endpoints the other modules expose at
 * `/q/health`. Nothing in the benchmark pipeline calls these (time-to-first-request polls
 * `TARGET_URL` instead), they exist for parity when poking at a running app by hand.
 */
@Controller('q')
export class HealthController {
  @Get('health')
  health(): Record<string, unknown> {
    return { status: 'UP', checks: [] };
  }

  @Get('health/live')
  live(): Record<string, unknown> {
    return { status: 'UP', checks: [] };
  }

  @Get('health/ready')
  ready(): Record<string, unknown> {
    return { status: 'UP', checks: [] };
  }
}

import { Body, Controller, Get, HttpCode, HttpStatus, Param, Post, Res, ValidationPipe } from '@nestjs/common';
import { Response } from 'express';

import { FruitDTO } from '../dto/fruit.dto';
import { FruitService } from '../service/fruit.service';

/**
 * Mirrors `org.acme.rest.FruitController`. The contract is the repo-wide `openapi.yml`.
 *
 * Two NestJS defaults have to be overridden to stay compatible with the other modules:
 *  - POST returns 200, not NestJS's default 201.
 *  - A missing fruit returns a bare 404 with an empty body; throwing `NotFoundException` would
 *    emit a `{"statusCode":404,...}` JSON body that the JAX-RS implementation does not send.
 */
@Controller('fruits')
export class FruitController {
  constructor(private readonly fruitService: FruitService) {}

  @Get()
  getAll(): Promise<FruitDTO[]> {
    return this.fruitService.getAllFruits();
  }

  @Get(':name')
  async getFruit(@Param('name') name: string, @Res() response: Response): Promise<void> {
    const fruit = await this.fruitService.getFruitByName(name);

    if (fruit === null || fruit === undefined) {
      response.status(HttpStatus.NOT_FOUND).end();
      return;
    }

    response.status(HttpStatus.OK).json(fruit);
  }

  // Validated here rather than through a global pipe, matching the Java module which only
  // validates the POST body (`@Valid`) - the GET endpoints pay no pipe-dispatch cost.
  @Post()
  @HttpCode(HttpStatus.OK)
  addFruit(@Body(new ValidationPipe({ transform: true })) fruit: FruitDTO): Promise<FruitDTO> {
    return this.fruitService.createFruit(fruit);
  }
}

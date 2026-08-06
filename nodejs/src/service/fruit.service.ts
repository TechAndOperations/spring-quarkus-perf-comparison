import { Injectable } from '@nestjs/common';
import { Span, SpanStatusCode, trace } from '@opentelemetry/api';

import { FruitDTO } from '../dto/fruit.dto';
import { fruitFromDto, fruitToDto } from '../mapping/fruit.mapper';
import { FruitRepository } from '../repository/fruit.repository';

const tracer = trace.getTracer('nodejs');

/** The `@WithSpan` equivalent used by `org.acme.service.FruitService`. */
function withSpan<T>(name: string, attributes: Record<string, string>, work: (span: Span) => Promise<T>): Promise<T> {
  return tracer.startActiveSpan(name, async (span) => {
    try {
      for (const [key, value] of Object.entries(attributes)) {
        span.setAttribute(key, value);
      }

      return await work(span);
    }
    catch (error) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: `${error}` });
      throw error;
    }
    finally {
      span.end();
    }
  });
}

/** Mirrors `org.acme.service.FruitService`. */
@Injectable()
export class FruitService {
  constructor(private readonly fruitRepository: FruitRepository) {}

  getAllFruits(): Promise<FruitDTO[]> {
    return withSpan('FruitService.getAllFruits', {}, async () => {
      const fruits = await this.fruitRepository.listAll();

      return fruits.map(fruitToDto);
    });
  }

  getFruitByName(name: string): Promise<FruitDTO> {
    return withSpan('FruitService.getFruitByName', { 'arg.name': name }, async () => {
      const fruit = await this.fruitRepository.findByName(name);

      return fruitToDto(fruit);
    });
  }

  createFruit(fruitDTO: FruitDTO): Promise<FruitDTO> {
    return withSpan('FruitService.createFruit', { 'arg.fruit': JSON.stringify(fruitDTO) }, async () => {
      const fruit = await this.fruitRepository.persist(fruitFromDto(fruitDTO));

      return fruitToDto(fruit);
    });
  }
}

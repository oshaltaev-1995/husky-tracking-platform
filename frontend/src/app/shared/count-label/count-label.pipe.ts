import { Pipe, PipeTransform } from '@angular/core';

export function countLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

@Pipe({
  name: 'countLabel',
  standalone: true,
})
export class CountLabelPipe implements PipeTransform {
  transform(count: number, singular: string, plural = `${singular}s`): string {
    return countLabel(count, singular, plural);
  }
}

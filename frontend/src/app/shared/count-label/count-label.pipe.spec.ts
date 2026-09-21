import { CountLabelPipe } from './count-label.pipe';

describe('CountLabelPipe', () => {
  const pipe = new CountLabelPipe();

  it('uses singular and plural labels', () => {
    expect(pipe.transform(1, 'record')).toBe('1 record');
    expect(pipe.transform(2, 'record')).toBe('2 records');
    expect(pipe.transform(1, 'person', 'people')).toBe('1 person');
    expect(pipe.transform(0, 'person', 'people')).toBe('0 people');
  });
});

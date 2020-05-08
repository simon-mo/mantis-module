local base = import 'base.libsonnet';

{
  'out.json':
    base.config(name='hi', cmdline=['a', 'b'],),
}

import zipfile, re
z = zipfile.ZipFile('output/SK9822_5x4.zip')
gtl = z.read('matrix-F_Cu.gtl').decode()
lines = gtl.split('\n')
last_x = last_y = None
for line in lines:
    line = line.strip()
    m = re.match(r'X(-?\d+)Y(-?\d+)D0([123])\*', line)
    if not m:
        continue
    x = int(m.group(1)) / 1_000_000
    y = int(m.group(2)) / 1_000_000
    op = int(m.group(3))
    if op == 2:
        last_x, last_y = x, y
    elif op == 1 and last_x is not None:
        if min(x, last_x) < 7.5:
            print(f'({last_x:.3f},{last_y:.3f}) -> ({x:.3f},{y:.3f})  dx={x-last_x:+.3f} dy={y-last_y:+.3f}')
        last_x, last_y = x, y

import sys
import os

def print_help():
    path = os.path.realpath(__file__)
    print(path + " <file>.swg")

def gen_intf(file):
    path = os.path.dirname(os.path.realpath(__file__))
    with open(file, 'r') as f:
        contents = f.readlines()

    idx = 0
    for c in contents:
        idx += 1
        if "%}" in c:
            break

    typemap_path = os.path.join(path, 'typemap.template')
    with open(typemap_path, 'r') as i_typemap:
        l_typemap = i_typemap.readlines()

    j = 0
    for i in range(idx, idx + len(l_typemap)):
        contents.insert(i, l_typemap[j])
        j += 1

    new_i_file = os.path.splitext(file)[0]+'.i'

    with open(new_i_file, 'w') as intf:
        contents = "".join(contents)
        intf.write(contents)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print_help()
        exit(1)

    gen_intf(sys.argv[1])

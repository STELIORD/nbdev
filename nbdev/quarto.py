# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/api/quarto.ipynb.

# %% ../nbs/api/quarto.ipynb 2
from __future__ import annotations
import subprocess,sys,shutil,ast,warnings,traceback
from os import system
from contextlib import contextmanager

from .config import *
from .doclinks import *

from fastcore.utils import *
from fastcore.script import call_parse
from fastcore.shutil import rmtree,move,copytree
from fastcore.meta import delegates
from .serve import proc_nbs,_proc_file
from . import serve_drv

# %% auto 0
__all__ = ['BASE_QUARTO_URL', 'install_quarto', 'install', 'nbdev_sidebar', 'refresh_quarto_yml', 'nbdev_proc_nbs',
           'nbdev_readme', 'nbdev_docs', 'prepare', 'fs_watchdog', 'nbdev_preview']

# %% ../nbs/api/quarto.ipynb 4
def _sprun(cmd):
    try: subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as cpe: sys.exit(cpe.returncode)

# %% ../nbs/api/quarto.ipynb 6
BASE_QUARTO_URL='https://www.quarto.org/download/latest/'

def _install_linux():
    system(f'curl -LO {BASE_QUARTO_URL}quarto-linux-amd64.deb')
    system('sudo dpkg -i quarto-linux-amd64.deb && rm quarto-linux-amd64.deb')
    
def _install_mac():
    system(f'curl -LO {BASE_QUARTO_URL}quarto-macos.pkg')
    system('sudo installer -pkg quarto-macos.pkg -target / && rm quarto-macos.pkg')

@call_parse
def install_quarto():
    "Install latest Quarto on macOS or Linux, prints instructions for Windows"
    if sys.platform not in ('darwin','linux'):
        return print('Please visit https://quarto.org/docs/get-started/ to install quarto')
    print("Installing or upgrading quarto -- this requires root access.")
    system('sudo touch .installing')
    try:
        installing = Path('.installing')
        if not installing.exists(): return print("Cancelled. Please download and install Quarto from quarto.org.")
        if 'darwin' in sys.platform: _install_mac()
        elif 'linux' in sys.platform: _install_linux()
    finally: system('sudo rm -f .installing')

# %% ../nbs/api/quarto.ipynb 7
@call_parse
def install():
    "Install Quarto and the current library"
    install_quarto.__wrapped__()
    d = get_config().lib_path
    if (d/'__init__.py').exists(): system(f'pip install -e "{d.parent}[dev]"')

# %% ../nbs/api/quarto.ipynb 9
def _pre(p,b=True): return '    ' * (len(p.parts)) + ('- ' if b else '  ')
def _sort(a):
    x,y = a
    if y.startswith('index.'): return x,'00'
    return a
#|export
_def_file_re = '\.(?:ipynb|qmd|html)$'

@delegates(nbglob_cli)
def _nbglob_docs(
    path:str=None, # Path to notebooks
    file_glob:str=None, # Only include files matching glob    
    file_re:str=_def_file_re, # Only include files matching regex
    **kwargs):
    return nbglob(path, file_glob=file_glob, file_re=file_re, **kwargs)

# %% ../nbs/api/quarto.ipynb 10
@call_parse
@delegates(_nbglob_docs)
def nbdev_sidebar(
    path:str=None, # Path to notebooks
    printit:bool=False,  # Print YAML for debugging
    force:bool=False,  # Create sidebar even if settings.ini custom_sidebar=False
    skip_folder_re:str='(?:^[_.]|^www\$)', # Skip folders matching regex
    **kwargs):
    "Create sidebar.yml"
    if not force and get_config().custom_sidebar: return
    path = get_config().nbs_path if not path else Path(path)
    def _f(a,b): return Path(a),b
    files = nbglob(path, func=_f, skip_folder_re=skip_folder_re, **kwargs).sorted(key=_sort)
    lastd,res = Path(),[]
    for dabs,name in files:
        drel = dabs.relative_to(path)
        d = Path()
        for p in drel.parts:
            d /= p
            if d == lastd: continue
            title = re.sub('^\d+_', '', d.name)
            res.append(_pre(d.parent) + f'section: {title}')
            res.append(_pre(d.parent, False) + 'contents:')
            lastd = d
        res.append(f'{_pre(d)}{d.joinpath(name)}')

    yml_path = path/'sidebar.yml'
    yml = "website:\n  sidebar:\n    contents:\n"
    yml += '\n'.join(f'      {o}' for o in res)+'\n'
    if printit: return print(yml)
    yml_path.write_text(yml)

# %% ../nbs/api/quarto.ipynb 13
_quarto_yml="""project:
  type: website

format:
  html:
    theme: cosmo
    css: styles.css
    toc: true

website:
  twitter-card: true
  open-graph: true
  repo-actions: [issue]
  navbar:
    background: primary
    search: true
  sidebar:
    style: floating

metadata-files: [nbdev.yml, sidebar.yml]"""

# %% ../nbs/api/quarto.ipynb 14
_nbdev_yml="""project:
  output-dir: {doc_path}

website:
  title: "{title}"
  site-url: "{doc_host}{doc_baseurl}"
  description: "{description}"
  repo-branch: {branch}
  repo-url: "{git_url}"
"""

# %% ../nbs/api/quarto.ipynb 15
def refresh_quarto_yml():
    "Generate `_quarto.yml` from `settings.ini`."
    cfg = get_config()
    ny = cfg.nbs_path/'nbdev.yml'
    vals = {k:cfg[k] for k in ['title', 'description', 'branch', 'git_url', 'doc_host', 'doc_baseurl']}
    vals['doc_path'] = cfg.doc_path.name
    if 'title' not in vals: vals['title'] = vals['lib_name']
    ny.write_text(_nbdev_yml.format(**vals))
    qy = cfg.nbs_path/'_quarto.yml'
    if 'custom_quarto_yml' in cfg.d: print("NB: `_quarto.yml` is no longer auto-updated. Remove `custom_quarto_yml` from `settings.ini`")
    if qy.exists() and not str2bool(cfg.get('custom_quarto_yml', True)): qy.unlink()
    if not qy.exists(): qy.write_text(_quarto_yml)

# %% ../nbs/api/quarto.ipynb 16
def _ensure_quarto():
    if shutil.which('quarto'): return
    print("Quarto is not installed. We will download and install it for you.")
    install.__wrapped__()

# %% ../nbs/api/quarto.ipynb 17
def _pre_docs(path=None, n_workers:int=defaults.cpus, **kwargs):
    cfg = get_config()
    path = Path(path) if path else cfg.nbs_path
    _ensure_quarto()
    refresh_quarto_yml()
    import nbdev.doclinks
    nbdev.doclinks._build_modidx()
    nbdev_sidebar.__wrapped__(path=path, **kwargs)
    cache = proc_nbs(path, n_workers=n_workers, **kwargs)
    return cache,cfg,path

# %% ../nbs/api/quarto.ipynb 18
@call_parse
@delegates(proc_nbs)
def nbdev_proc_nbs(**kwargs):
    "Process notebooks in `path` for docs rendering"
    _pre_docs(**kwargs)[0]

# %% ../nbs/api/quarto.ipynb 20
def _copytree(a,b):
    if sys.version_info.major >=3 and sys.version_info.minor >=8: copytree(a, b, dirs_exist_ok=True)
    else:
        from distutils.dir_util import copy_tree
        copy_tree(a, b)

# %% ../nbs/api/quarto.ipynb 21
@call_parse
def nbdev_readme(
    path:str=None, # Path to notebooks
    chk_time:bool=False): # Only build if out of date
    cfg = get_config()
    cfg_path = cfg.config_path
    path = Path(path) if path else cfg.nbs_path
    idx_path = path/cfg.readme_nb
    if not idx_path.exists(): return print(f"Could not find {idx_path}")
    readme_path = cfg_path/'README.md'
    if chk_time and readme_path.exists() and readme_path.stat().st_mtime>=idx_path.stat().st_mtime: return

    yml_path = path/'sidebar.yml'
    moved=False
    if yml_path.exists():
        # move out of the way to avoid rendering whole website
        yml_path.rename(path/'sidebar.yml.bak')
        moved=True

    try:
        cache = proc_nbs(path)
        idx_cache = cache/cfg.readme_nb
        _sprun(f'cd "{cache}" && quarto render "{idx_cache}" -o README.md -t gfm --no-execute')
    finally:
        if moved: (path/'sidebar.yml.bak').rename(yml_path)
    tmp_doc_path = cache/cfg.doc_path.name
    readme = tmp_doc_path/'README.md'
    if readme.exists():
        _rdmi = tmp_doc_path/(idx_cache.stem + '_files')
        if readme_path.exists(): readme_path.unlink() # py37 doesn't have `missing_ok`
        move(readme, cfg_path)
        if _rdmi.exists(): _copytree(_rdmi, cfg_path/_rdmi.name, dirs_exist_ok=True) # Supporting files for README

# %% ../nbs/api/quarto.ipynb 23
@call_parse
@delegates(_nbglob_docs)
def nbdev_docs(
    path:str=None, # Path to notebooks
    n_workers:int=defaults.cpus,  # Number of workers
    **kwargs):
    "Create Quarto docs and README.md"
    cache,cfg,path = _pre_docs(path, n_workers=n_workers, **kwargs)
    nbdev_readme.__wrapped__(path=path, chk_time=True)
    _sprun(f'cd "{cache}" && quarto render --no-cache')
    shutil.rmtree(cfg.doc_path, ignore_errors=True)
    move(cache/cfg.doc_path.name, cfg.config_path)

# %% ../nbs/api/quarto.ipynb 25
@call_parse
def prepare():
    "Export, test, and clean notebooks, and render README if needed"
    import nbdev.test, nbdev.clean
    nbdev_export.__wrapped__()
    nbdev.test.nbdev_test.__wrapped__()
    nbdev.clean.nbdev_clean.__wrapped__()
    refresh_quarto_yml()
    nbdev_readme.__wrapped__(chk_time=True)

# %% ../nbs/api/quarto.ipynb 27
@contextmanager
def fs_watchdog(func, path, recursive:bool=True):
    "File system watchdog dispatching to `func`"
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    class _ProcessHandler(FileSystemEventHandler): dispatch=func
    observer = Observer()
    observer.schedule(_ProcessHandler, path, recursive=True)
    observer.start()
    try: yield
    except KeyboardInterrupt: pass
    finally:
        observer.stop()
        observer.join()

# %% ../nbs/api/quarto.ipynb 28
@call_parse
@delegates(_nbglob_docs)
def nbdev_preview(
    path:str=None, # Path to notebooks
    port:int=None, # The port on which to run preview
    host:str=None, # The host on which to run preview
    n_workers:int=defaults.cpus,  # Number of workers
    **kwargs):
    "Preview docs locally"
    os.environ['QUARTO_PREVIEW']='1'
    cache,cfg,path = _pre_docs(path, n_workers=n_workers, **kwargs)
    xtra = []
    if port: xtra += ['--port', str(port)]
    if host: xtra += ['--host', host]

    def _f(e):
        res = _proc_file(Path(e.src_path), cache, path)
        if res:
            try: serve_drv.main(res)
            except: traceback.print_exc()

    os.chdir(cache)
    xtra = xtra or []
    with fs_watchdog(_f, path): subprocess.run(['quarto','preview']+xtra)

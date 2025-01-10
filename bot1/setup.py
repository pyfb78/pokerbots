from setuptools import setup
from setuptools.extension import Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        "ompeval",
        ["ompeval.pyx"],
        libraries=["ompeval"],  # Link against the OMPEval library
        library_dirs=["OMPEval"],  # Path to OMPEval library
        include_dirs=["OMPEval/omp/"],  # Path to headers
        language="c++",
    )
]

setup(
    ext_modules=cythonize(extensions),
)


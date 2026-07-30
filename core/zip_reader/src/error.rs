use pyo3::exceptions::{PyIOError, PyRuntimeError, PyValueError};
use pyo3::PyErr;

#[derive(thiserror::Error, Debug)]
pub enum ApexZipError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("archive error: {0}")]
    Zip(#[from] zip::result::ZipError),

    #[error("{0}")]
    Bounds(String),
}

impl From<ApexZipError> for PyErr {
    fn from(err: ApexZipError) -> PyErr {
        match err {
            ApexZipError::Io(e) => PyIOError::new_err(e.to_string()),
            ApexZipError::Zip(e) => PyValueError::new_err(e.to_string()),
            ApexZipError::Bounds(msg) => PyRuntimeError::new_err(msg),
        }
    }
}

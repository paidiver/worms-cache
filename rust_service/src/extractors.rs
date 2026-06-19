//! Custom Axum extractor that uses `serde_qs` for query-string parsing.
//!
//! Unlike the built-in `axum::extract::Query`, this extractor correctly handles
//! repeated keys such as `aphia_ids[]=1&aphia_ids[]=2`.

use axum::extract::FromRequestParts;
use axum::http::request::Parts;
use serde::de::DeserializeOwned;

pub struct QsQuery<T>(pub T);

#[async_trait::async_trait]
impl<T, S> FromRequestParts<S> for QsQuery<T>
where
    T: DeserializeOwned,
    S: Send + Sync,
{
    type Rejection = crate::errors::AppError;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let query = parts.uri.query().unwrap_or_default();
        let value = serde_qs::from_str::<T>(query)
            .map_err(|e| crate::errors::AppError::BadRequest(e.to_string()))?;
        Ok(QsQuery(value))
    }
}

export const PROTOCOL_PREFIX = "http://";
export const JSON_HTTP_HEADER_VALUE = "application/json";
export const HTTP_POST_METHOD = "POST";
export const HTTP_DELETE_METHOD = "DELETE";

/**
 * check if error code is in response data and throws appropriate error if so.
 * @param {object} data Response object
 */
export function checkErrorCode(data) {
  if (!("error_code" in data)) {
    return;
  }
  if ("message" in data) {
    throw new Error(`${data.error_code}: ${data.message}`);
  }
}

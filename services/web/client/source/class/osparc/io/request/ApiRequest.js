/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 * HTTP requests to simcore's rest API
 */
qx.Class.define("osparc.io.request.ApiRequest", {
  extend: qx.io.request.Xhr,

  construct: function(url, method) {
    const baseURL = osparc.io.rest.AbstractResource.API;

    this.base(arguments, baseURL+url, method);
    this.set({
      accept: "application/json"
    });

    this.setRequestHeader("Content-Type", "application/json");
  }
});

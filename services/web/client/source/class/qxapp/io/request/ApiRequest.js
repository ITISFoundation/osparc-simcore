/**
 * HTTP requests to simcore's rest API
 *
*/
qx.Class.define("qxapp.io.request.ApiRequest", {
  extend: qx.io.request.Xhr,

  construct: function(url, method) {
    const prefix = qxapp.io.rest.AbstractResource.API;

    this.base(arguments, prefix+url, method);
    this.set({
      accept: "application/json"
    });

    this.setRequestHeader("Content-Type", "application/json");
  }

  // events:
  // {
  //    "responded": "qx.eventy.type.Data"
  // }
});

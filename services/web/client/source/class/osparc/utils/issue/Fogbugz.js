/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const url = osparc.utils.issue.Fogbugz.getNewIssueUrl();
 *   window.open(url);
 * </pre>
 */

qx.Class.define("osparc.utils.issue.Fogbugz", {
  type: "static",

  statics: {
    getNewIssueUrl: function(statics_data) {
      const product = qx.core.Environment.get("product.name");

      url_head = statics_data.fogbugzNewcaseUrl;
      switch (project){
        case "s4l":
          url_head = statics_data.s4lFogbugzNewcaseUrl;
          break;
        case "tis":
          url_head = statics_data.tisFogbugzNewcaseUrl;
          break;
      }

      if (url_head){
        const body = osparc.utils.issue.Base.getBody();
        const url = url_head + "&sEvent=" + body;
        return url
      }
      return undefined;
    }
  }
});

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
    getNewIssueUrl: function(staticsData) {
      const product = qx.core.Environment.get("product.name");

      let urlHead = staticsData.osparcIssuesNewUrl;
      switch (product) {
        case "s4l":
        case "s4llite":
          urlHead = staticsData.s4lIssuesNewUrl;
          break;
        case "tis":
          urlHead = staticsData.tisIssuesNewUrl;
          break;
      }

      if (urlHead) {
        const body = osparc.utils.issue.Base.getBody();
        const url = urlHead + "&sEvent=" + body;
        return url;
      }
      return undefined;
    }
  }
});

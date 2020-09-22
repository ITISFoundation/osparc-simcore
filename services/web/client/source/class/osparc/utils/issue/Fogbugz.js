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
    getNewIssueUrl: function(originUrl, prjId) {
      const body = osparc.utils.issue.Base.getBody();

      let url = originUrl + "/f/cases/new";
      url += "?command=new";
      url += "&ixProject=" + prjId;
      url += "&sEvent=" + body;
      return url;
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const url = osparc.utils.issue.Github.getNewIssueUrl();
 *   window.open(url);
 * </pre>
 */

qx.Class.define("osparc.utils.issue.Github", {
  type: "static",

  statics: {
    getNewIssueUrl: function() {
      const body = osparc.utils.issue.Base.getBody();

      let url = "https://github.com/ITISFoundation/osparc-issues/issues/new";
      url += "?labels=Feedback";
      url += "&projects=ITISFoundation/3";
      url += "&body=" + body;
      return url;
    }
  }
});

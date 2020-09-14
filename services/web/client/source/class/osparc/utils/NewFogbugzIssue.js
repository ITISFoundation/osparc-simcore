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
 *   const url = osparc.utils.NewFogbugzIssue.getNewIssueUrl();
 *   window.open(url);
 * </pre>
 */

qx.Class.define("osparc.utils.NewFogbugzIssue", {
  type: "static",

  statics: {
    getNewIssueUrl: function() {
      const temp = osparc.utils.NewFogbugzIssue.getTemplate();
      let env = "```json\n";
      env += JSON.stringify(osparc.utils.LibVersions.getEnvLibs(), null, 2);
      env += "\n```";
      const body = encodeURIComponent(temp+env);
      let url = "https://z43.fogbugz.com/f/cases/new";
      url += "?command=new";
      url += "&ixProject=45";
      url += "&sEvent=" + body;
      return url;
    },

    getTemplate: function() {
      return `
## Long story short
<!-- Please describe your review or bug you found. -->

## Expected behaviour
<!-- What is the behaviour you expect? -->

## Actual behaviour
<!-- What's actually happening? -->

## Steps to reproduce
<!-- Please describe steps to reproduce the issue. -->

Note: your environment was attached but will not be displayed
<!--
## Your environment
`;
    }
  }
});

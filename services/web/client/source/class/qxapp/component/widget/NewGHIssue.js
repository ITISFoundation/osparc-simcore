/* ************************************************************************

   qxapp - the simcore frontend

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
 *   const url = qxapp.component.widget.NewGHIssue.getNewIssueUrl();
 *   window.open(url);
 * </pre>
 */

qx.Class.define("qxapp.component.widget.NewGHIssue", {
  type: "static",

  statics: {
    getNewIssueUrl: function() {
      const temp = qxapp.component.widget.NewGHIssue.getTemplate();
      let env = "```json\n";
      env += JSON.stringify(qxapp.utils.LibVersions.getEnvLibs(), null, 2);
      env += "\n```";
      const body = encodeURIComponent(temp+env);
      let url = "https://github.com/ITISFoundation/osparc-simcore/issues/new";
      url += "?labels=tester_review,UX_improvemnts";
      url += "&projects=ITISFoundation/3";
      url += "&body=" + body;
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

## Your environment
`;
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/* global CodeMirror */

/**
 * @asset(code-mirror/codemirror.min.js)
 * @asset(code-mirror/python.min.js)
 * @asset(code-mirror/javascript.min.js)
 * @asset(code-mirror/codemirror.min.css)
 * @asset(code-mirror/3024-day.min.css)
 * @asset(code-mirror/3024-night.min.css)
 * @ignore(CodeMirror)
 */

/**
 * A qooxdoo wrapper for
 * <a href='https://github.com/codemirror/CodeMirror' target='_blank'>CodeMirror</a>
 */

qx.Class.define("osparc.wrapper.CodeMirror", {
  extend: qx.core.Object,
  type: "singleton",

  statics: {
    NAME: "CodeMirror",
    VERSION: "5.62.3",
    URL: "https://github.com/codemirror/CodeMirror"
  },

  construct: function() {
    this.base(arguments);
  },

  properties: {
    libReady: {
      nullable: false,
      init: false,
      check: "Boolean"
    }
  },

  members: {
    init: function() {
      // initialize the script loading
      const codeMirrorPath = "code-mirror/codemirror.min.js";
      const pythonHLPath = "code-mirror/python.min.js";
      const javascriptHLPath = "code-mirror/javascript.min.js";
      const codeMirrorCss = "code-mirror/codemirror.min.css";
      const codeMirrorDayCss = "code-mirror/3024-day.min.css";
      const codeMirrorNightCss = "code-mirror/3024-night.min.css";
      const codeMirrorCssUri = qx.util.ResourceManager.getInstance().toUri(codeMirrorCss);
      const codeMirrorDayCssUri = qx.util.ResourceManager.getInstance().toUri(codeMirrorDayCss);
      const codeMirrorNightCssUri = qx.util.ResourceManager.getInstance().toUri(codeMirrorNightCss);
      qx.module.Css.includeStylesheet(codeMirrorCssUri);
      qx.module.Css.includeStylesheet(codeMirrorDayCssUri);
      qx.module.Css.includeStylesheet(codeMirrorNightCssUri);
      const dynLoader = new qx.util.DynamicScriptLoader([
        codeMirrorPath,
        pythonHLPath,
        javascriptHLPath
      ]);

      dynLoader.addListenerOnce("ready", e => {
        console.log(codeMirrorPath + " loaded");
        this.setLibReady(true);
      }, this);

      dynLoader.addListener("failed", e => {
        let data = e.getData();
        console.error("failed to load " + data.script);
      }, this);

      dynLoader.start();
    },

    convertTextArea: function(textArea) {
      const el = textArea.getContentElement().getDomElement();
      // eslint-disable-next-line new-cap
      const cm = new CodeMirror.fromTextArea(el, {
        lineNumbers: true,
        mode: "python",
        theme: "3024-night"
      });

      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => {
      });
      return cm;
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */
/* eslint-disable no-use-before-define */

/**
 * Display widget with a title bar and collapsible content.
 */
qx.Class.define("osparc.desktop.PanelView", {
  extend: osparc.widget.CollapsibleView,

  construct: function(title, content) {
    this.base(arguments, title, content);

    // Title bar
    this.getTitleBar().set({
      appearance: "panelview-titlebar"
    });
  },

  properties: {
    appearance: {
      init: "panelview",
      refine: true
    }
  },

  members: {
    // override
    _applyContent: function(content, oldContent) {
      this.base(arguments, content, oldContent);

      this._innerContainer.set({
        appearance: "panelview-content"
      });
    }
  }
});

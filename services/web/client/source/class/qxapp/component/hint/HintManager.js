/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * @asset(hint/hint.css)
 */

qx.Class.define("qxapp.component.hint.HintManager", {
  extend: qx.core.Object,
  type: "singleton",
  statics: {
    getHint: function(element, text) {
      return this.getInstance().getHint(element, text);
    }
  },
  members: {
    getHint(element, text) {
      const hint = new qxapp.ui.hint.Hint(element, text);
      return hint;
    }
  }
});

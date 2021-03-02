/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2021 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Odei Maiz (odeimaiz)
 */

/**
 * A toolbar split button that serves to fetch or load some data from the server. To indicate that some processing is being done, and
 * that the user has to wait, a rotating special icon is shown meanwhile.
 */
qx.Class.define("osparc.ui.toolbar.FetchSplitButton", {
  extend: qx.ui.toolbar.SplitButton,
  include: osparc.ui.mixin.FetchButton,

  members: {
    // overridden
    _createChildControlImpl : function(id, hash) {
      let control;

      switch (id) {
        case "button":
          control = new osparc.ui.form.FetchButton();
          control.addListener("execute", this._onButtonExecute, this);
          control.setFocusable(false);
          this._addAt(control, 0, {flex: 1});
          break;
      }

      return control || this.base(arguments, id);
    }
  }
});

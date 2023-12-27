/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.desktop.credits.DateFilters", {
  extend: qx.ui.core.Widget,
  construct() {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(7));
    this._buildLayout();
  },
  events: {
    "change": "qx.event.type.Data"
  },
  members: {
    _buildLayout() {
      this._removeAll();
      this.__from = this.__addDateInput("From");
      this.__until = this.__addDateInput("Until");
      const lastWeekBtn = new qx.ui.form.Button("Last week").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      lastWeekBtn.addListener("execute", () => {
        const today = new Date();
        const lastWeek = new Date(today);
        lastWeek.setDate(today.getDate() - 7)
        this.__from.setValue(lastWeek);
        this.__until.setValue(today);
      })
      this._add(lastWeekBtn);
      const lastMonthBtn = new qx.ui.form.Button("Last month").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      lastMonthBtn.addListener("execute", () => {
        const today = new Date();
        const lastMonth = new Date(today);
        lastMonth.setMonth(today.getMonth() - 1);
        this.__from.setValue(lastMonth);
        this.__until.setValue(today);
      })
      this._add(lastMonthBtn);
      const lastYearBtn = new qx.ui.form.Button("Last year").set({
        allowStretchY: false,
        alignY: "bottom"
      });
      lastYearBtn.addListener("execute", () => {
        const today = new Date();
        const lastYear = new Date(today);
        lastYear.setYear(today.getFullYear() - 1);
        this.__from.setValue(lastYear);
        this.__until.setValue(today);
      })
      this._add(lastYearBtn);
    },
    __addDateInput(label) {
      const container = new qx.ui.container.Composite(new qx.ui.layout.VBox());
      const lbl = new qx.ui.basic.Label(label);
      container.add(lbl);
      const datepicker = new qx.ui.form.DateField();
      datepicker.setValue(new Date());
      datepicker.addListener("changeValue", () => this._changeHandler())
      container.add(datepicker);
      this._add(container);
      return datepicker;
    },
    _changeHandler() {
      const from =  this._getFormattedDate(this.__from.getValue());
      const until =  this._getFormattedDate(this.__until.getValue());
      this.fireDataEvent("change", {
        from,
        until
      });
    },
    _getFormattedDate(date) {
      const offset = date.getTimezoneOffset();
      const ret = new Date(date.getTime() - (offset*60*1000));
      return ret.toISOString().split("T")[0]
    }
  }
});

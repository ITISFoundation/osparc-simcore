/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.support.Conversations", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));
    this.__conversationListItems = [];

    this.__filterButtons = [];
    this.__filterButtons.push(this.getChildControl("filter-all-button"));
    if (osparc.store.Groups.getInstance().amIASupportUser()) {
      this.__filterButtons.push(this.getChildControl("filter-open-button"));
    } else {
      this.__filterButtons.push(this.getChildControl("filter-unread-button"));
    }

    this.__fetchConversations();

    this.__listenToNewConversations();
  },

  properties: {
    currentFilter: {
      check: [
        "all",
        "unread",
        "open",
      ],
      init: "all",
      event: "changeCurrentFilter",
      apply: "__applyCurrentFilter",
    },
  },

  events: {
    "openConversation": "qx.event.type.Data",
  },

  statics: {
    FILTER_BUTTON_AESTHETIC: {
      appearance: "filter-toggle-button",
      allowGrowX: false,
      paddingTop: 4,
      paddingBottom: 4,
    },
  },

  members: {
    __conversationListItems: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "filters-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(4));
          this._add(control);
          break;
        case "filter-all-button":
          control = new qx.ui.form.ToggleButton(this.tr("All"));
          control.set({
            value: true,
            toolTipText: this.tr("Show all conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => this.setCurrentFilter("all"));
          this.getChildControl("filters-layout").add(control);
          break;
        case "filter-unread-button":
          control = new qx.ui.form.ToggleButton(this.tr("Unread"));
          control.set({
            toolTipText: this.tr("Show only unread conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => this.setCurrentFilter("unread"));
          this.getChildControl("filters-layout").add(control);
          break;
        case "filter-open-button":
          control = new qx.ui.form.ToggleButton(this.tr("Open"));
          control.set({
            toolTipText: this.tr("Show only open conversations"),
            ...this.self().FILTER_BUTTON_AESTHETIC,
          });
          control.addListener("execute", () => this.setCurrentFilter("open"));
          this.getChildControl("filters-layout").add(control);
          break;
        case "loading-button":
          control = new osparc.ui.form.FetchButton();
          this._add(control);
          break;
        case "conversations-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
      }

      return control || this.base(arguments, id);
    },

    __applyCurrentFilter: function(filter) {
      this.__filterButtons.forEach(button => {
        button.setValue(false);
      });

      this.__conversationListItems.forEach(conversationItem => {
        const conversation = conversationItem.getConversation();
        switch (filter) {
          case "all":
            this.getChildControl("filter-all-button").setValue(true);
            conversationItem.show();
            break;
          case "unread":
            this.getChildControl("filter-unread-button").setValue(true);
            if (osparc.store.Groups.getInstance().amIASupportUser()) {
              if (conversation.getReadBySupport()) {
                conversationItem.exclude();
              } else {
                conversationItem.show();
              }
            } else {
              if (conversation.getReadByUser()) {
                conversationItem.exclude();
              } else {
                conversationItem.show();
              }
            }
            break;
          case "open":
            this.getChildControl("filter-open-button").setValue(true);
            if (conversation.getResolved() === false) {
              conversationItem.show();
            } else {
              conversationItem.exclude();
            }
            break;
        }
      });
    },

    __getConversationItem: function(conversationId) {
      return this.__conversationListItems.find(conversation => conversation.getConversation().getConversationId() === conversationId);
    },

    __fetchConversations: function() {
      const loadMoreButton = this.getChildControl("loading-button");
      loadMoreButton.setFetching(true);

      osparc.store.ConversationsSupport.getInstance().fetchConversations()
        .then(conversations => {
          if (conversations.length) {
            conversations.forEach(conversation => this.__addConversation(conversation));
          }
          this.__sortConversations();
        })
        .finally(() => {
          loadMoreButton.setFetching(false);
          loadMoreButton.exclude();
        });
    },

    __listenToNewConversations: function() {
      osparc.store.ConversationsSupport.getInstance().addListener("conversationCreated", e => {
        const conversation = e.getData();
        this.__addConversation(conversation);
        this.__sortConversations();
      });
    },

    __addConversation: function(conversation) {
      // ignore it if it was already there
      const conversationId = conversation.getConversationId();
      const conversationItemFound = this.__getConversationItem(conversationId);
      if (conversationItemFound) {
        return null;
      }

      const conversationListItem = new osparc.support.ConversationListItem();
      conversationListItem.setConversation(conversation);
      conversationListItem.addListener("tap", () => this.fireDataEvent("openConversation", conversationId, this));
      conversation.addListener("changeModified", () => this.__sortConversations(), this);
      if (osparc.store.Groups.getInstance().amIASupportUser()) {
        conversation.addListener("changeReadBySupport", () => this.__applyCurrentFilter(this.getCurrentFilter()), this);
      } else {
        conversation.addListener("changeReadByUser", () => this.__applyCurrentFilter(this.getCurrentFilter()), this);
      }
      conversation.addListener("changeResolved", () => this.__applyCurrentFilter(this.getCurrentFilter()), this);
      this.__conversationListItems.push(conversationListItem);
      return conversationListItem;
    },

    __sortConversations: function() {
      const conversationsLayout = this.getChildControl("conversations-layout");
      conversationsLayout.removeAll();
      // sort them by modified date (newest first)
      this.__conversationListItems.sort((a, b) => {
        const aDate = new Date(a.getConversation().getModified());
        const bDate = new Date(b.getConversation().getModified());
        return bDate - aDate;
      });
      this.__conversationListItems.forEach(item => conversationsLayout.add(item));
    },
  },
});

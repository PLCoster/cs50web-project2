var socket;


document.addEventListener('DOMContentLoaded', () => {

  // Connect to websocket if not already connected:
  if (!io.connect().connected) {
    socket = io();
  }

  // SOCKET.IO Connection:
  socket.on('connect', () => {

    // Configure message input form, workspace and channel creation forms:
    message_config();
    new_channel_ws_config();
    logout_config();

    console.log('trying to join workspace')

    // Set up local storage via server:
    socket.emit('initial logon')

    // Connect user to their last workspace and channel:
    socket.emit('join workspace', {'sign in': true});
  });


  /*
  =============================================
  SOCKET IO FUNCTIONS
  =============================================
  */

  socket.on('local storage setup', data => {
    // On initial log on, set up local storage for app functionality:

    localStorage.setItem('user_id', data['user_id']);
  });

  socket.on('workspace logon', data => {
    // When a new workspace is joined, update workspace info:
    document.querySelector('#curr-workspace-show').innerHTML = data['workspace_name'] + ' \u23F7'
    document.querySelector('#curr-workspace-hide').innerHTML = data['workspace_name'] + ' \u23F6'
  });

  // When a new channel is joined, clear messages and display message history:
  socket.on('channel logon', data => {

    // Clear current messages
    document.querySelector('#messages').innerHTML = '';

    // Update current channel title
    document.querySelector('#curr-channel').innerHTML= data['channel_name'];

    // Add all new messages:
    for (let i = 0; i < data['message_history'].length ; i++) {
      message = data['message_history'][i]
      post_message(message)
    }
  });

  // When a new message is sent to the channel, add to the chat panel:
  socket.on('emit message', data => {
    console.log('Message received, message data:', data);
    post_message(data['message'])
  });

  // When a message is deleted in the current channel, remove message text:
  socket.on('emit deleted message', data => {
    console.log('Message deletion request received:', data);

    // Select the correct message
    messages = document.querySelectorAll('.user-message');

    for (let i = 0; i < messages.length; i++) {
      if (messages[i].dataset.message_id == data.message_id && messages[i].dataset.timestamp == data.timestamp) {
        messages[i].querySelector('.message-text').innerHTML = data.deleted_text;
        break;
      }
    }
  });

  // When a new channel is added, update channel link buttons
  socket.on('channel_list amended', data => {
    console.log('received updated channel list')
    channel_config(data.channel_list);
  });

  // When a new workspace is added, update workspace link buttons
  socket.on('workspace_list amended', data => {
    console.log('received updated workspace list');
    workspace_config(data.workspace_list);
  });

  // When a user joins or leaves a ws, update number of live users in ws:
  socket.on('ws_users amended', data => {
    console.log('updated user number received: ', data.users);
    document.querySelector('#workspace-users').innerHTML = data.users;
  });


  /*
  =============================================
  PAGE CONFIGURATION FUNCTIONS:
  =============================================
  */

  const message_config = function () {
    console.log('Message Config running')
    // Function to set up button to submit messages to the server:
    document.querySelector('#send-chat-input').onclick = () => {
      event.preventDefault();
      const message = document.querySelector('#message').value;
      console.log('Trying to send message to server:', message);
      if (message) {
        console.log('Sending Message: ', {'message': message});
        socket.emit('send message', {'message': message});
        document.querySelector('#message').value = '';
      }
    };
  };


  const channel_config = function (channel_list) {
    // Function to set up links to change channels:

    // Remove current channel list:
    document.querySelector('#channel-links').innerHTML = '';

    // Add all Channel Links:
    for (let i=0; i < channel_list.length; i++) {
      let channel_name = channel_list[i];

      const li = document.createElement('li');
      li.innerHTML = channel_name;
      li.className = 'channel-link';
      li.setAttribute('data-channel', channel_name);
      li.setAttribute('href', '');

      document.querySelector('#channel-links').append(li);
    }

    // Add onclick events to all Channel Links:
    document.querySelectorAll('.channel-link').forEach(button => {
      button.onclick = () => {
        event.preventDefault();
        console.log('You clicked on a channel link!')
        socket.emit('join channel', {'channel': button.dataset.channel});
        console.log('Channel now set to: ', button.dataset.channel);
      };
    });
  };


  const workspace_config = function (ws_list) {
    // Function to set up links to change workspaces:

    // Remove current workspace list:
    document.querySelector('#workspace-links').innerHTML = '';

    // Add all WS Links:
    for (let i=0; i < ws_list.length; i++) {
      let ws_name = ws_list[i];

      const li = document.createElement('li');
      li.innerHTML = ws_name;
      li.className = 'ws-link';
      li.setAttribute('data-workspace', ws_name);
      li.setAttribute('href', '');

      document.querySelector('#workspace-links').append(li);
    }

    // Add onclick events to all Channel Links:
    document.querySelectorAll('.ws-link').forEach(button => {
      button.onclick = () => {
        event.preventDefault();
        console.log('You clicked on a workspace link!')
        socket.emit('join workspace', {'sign in': false, 'workspace': button.dataset.workspace});
        console.log('Workspace now set to: ', button.dataset.workspace);
      };
    });
  };


  const new_channel_ws_config = function () {
    // Function to set up form to create new channel in a workspace

    // Set up sidebar onclick display of channel creator:
    document.querySelector('#channel-options-display').onclick = function() {
      document.querySelector('#new-channel').style.display = 'block';
      document.querySelector('#channel-links').style.display = 'none';
      document.querySelector('#channel-options-hide').style.display = 'block';
      this.style.display = 'none';
      }

    // Set up sidebar hiding of channel creator form:
    document.querySelector('#channel-options-hide').onclick = function () {
      document.querySelector('#new-channel').style.display = 'none';
      document.querySelector('#channel-links').style.display = 'block';
      document.querySelector('#channel-options-display').style.display = 'block';
      this.style.display = 'none';
    }

    // Set up new channel creator form:
    document.querySelector('#new-channel>button').onclick = () => {
      event.preventDefault();
      const new_channel = document.querySelector('#channel-name').value;
      if (new_channel) {
        console.log('trying to create new channel: ', new_channel);
        socket.emit('create channel', {'new_channel': new_channel});
        document.querySelector('#channel-options-hide').click();
        document.querySelector('#channel-name').value = '';
      }
    };

    // Set up sidebar onclick display of workspace creator:
    document.querySelector('#workspace-options-display').onclick = function() {
      document.querySelector('#new-workspace').style.display = 'block';
      document.querySelector('#workspace-options-hide').style.display = 'block';
      document.querySelector('#curr-workspace-panel').style.display = 'none';
      this.style.display = 'none';
    };

    // Set up sidebar onclick hiding of workspace creator form:
    document.querySelector('#workspace-options-hide').onclick = function () {
      document.querySelector('#new-workspace').style.display = 'none';
      document.querySelector('#workspace-options-display').style.display = 'block';
      document.querySelector('#curr-workspace-panel').style.display = 'block';
      this.style.display = 'none';
    };

    // Set up clickable display of users workspaces:
    document.querySelector('#curr-workspace-show').onclick = function () {
      document.querySelector('#workspace-links').style.display = 'block';
      document.querySelector('#curr-workspace-hide').style.display = 'block';
      this.style.display = 'none';
    };

    // Set up clickable hiding of users workspaces:
    document.querySelector('#curr-workspace-hide').onclick = function () {
      document.querySelector('#workspace-links').style.display = 'none';
      document.querySelector('#curr-workspace-show').style.display = 'block';
      this.style.display = 'none';
    };

    // Set up new workspace creator form:
    document.querySelector('#new-workspace>button').onclick = () => {
      event.preventDefault();
      const new_ws = document.querySelector('#workspace-name').value;
      if (new_ws) {
        console.log('trying to create new workspace: ', new_ws);
        socket.emit('create workspace', {'new_workspace': new_ws});
        document.querySelector('#workspace-options-hide').click();
        document.querySelector('#workspace-name').value = '';
      }
    };
  };


  const logout_config = function () {
    // Function to configure log out button on chat screen

    document.querySelector('#logout').onclick = () => {
      event.preventDefault();
      socket.emit('log out');
      localStorage.clear();
      window.location.href = '/logout';
    };
  };
});


/*
  =============================================
  HELPER FUNCTIONS:
  =============================================
  */

const post_message = function (message) {
  // Helper function to post received messages to the chat panel

  let client_message;

  // Check if message is by the client or a different user:
  if (message[6] === parseInt(localStorage.getItem('user_id'))) {
    client_message = true;
  } else {
    client_message = false;
  }

  // Create message element using handlebars
  const template = Handlebars.compile(document.querySelector('#message-template').innerHTML);

  const content = template({'username' : message[1], 'date' : message[3], 'timestamp' : message[2], 'message' : message[0], 'image': message[5], 'user_id' : message[6], 'client_message' : client_message, 'message_id' : message[4]});

  // Add to messages element
  document.querySelector('#messages').innerHTML += content;
};


delete_message = function () {
  // Helper function to delete a clients own message from a chat page

  event.preventDefault();

  let message = event.target;
  let message_id = message.dataset.message_id;
  let timestamp = message.dataset.timestamp;

  console.log('Deleting message: ', message_id, timestamp);

  socket.emit('delete message', {'message_id': message_id, 'timestamp': timestamp});
};



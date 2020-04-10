document.addEventListener('DOMContentLoaded', () => {

  let screen_name, channel;

  // Connect to websocket if not already connected:
  if (!io.connect().connected) {
    var socket = io();
  }

  // When socket is connected, run script:
  socket.on('connect', () => {


    const message_config = function () {
        // Function to set up button to submit messages to the server:
      document.querySelectorAll('#vote > button').forEach(button => {
        button.onclick = () => {
            event.preventDefault();
            const message = document.querySelector('#message').value;
            if (message) {
              console.log('Sending Message: ', {'message': message, 'screen_name': screen_name, 'channel': localStorage.getItem('channel')});
              socket.emit('send message', {'message': message, 'screen_name': screen_name, 'channel': localStorage.getItem('channel')});
              document.querySelector('#message').value = '';
            }
        };
      });
      new_channel_config();
    };

    const channel_config = function (channel_list) {
      // Function to set up links to change channels:

      // Remove current channel list:
      document.querySelector('p#channel-links').innerHTML = '';

      // Add all Channel Links:
      for (let i=0; i < channel_list.length; i++) {
        let channel_name = channel_list[i];

        const a = document.createElement('a');
        a.innerHTML = channel_name;
        a.className = 'channel-link';
        a.setAttribute('data-channel', channel_name);
        a.setAttribute('href', '');

        document.querySelector('#channel-links').append(a);

      }

      // Add onclick events to all Channel Links:
      document.querySelectorAll('.channel-link').forEach(button => {
        button.onclick = () => {
          event.preventDefault();
          socket.emit("join channel", {"channel": button.dataset.channel, "previous": localStorage.getItem('channel')});
          localStorage.setItem('channel', button.dataset.channel);
          console.log('Channel now set to: ', localStorage.getItem('channel'));
        };
      });
    };

    const new_channel_config = function () {
      // Function to set up new channel creator form:
      document.querySelector('#new-channel').onclick = () => {
        event.preventDefault();
        const new_channel = document.querySelector('#channel-name').value;
        if (new_channel) {
          socket.emit('create channel', {'new_channel': new_channel});
        }
        document.querySelector('#channel-name').value = '';
      };
    };

    // Log in form should set username and then hide login and display vote buttons
    // Only visible if there is no username in local storage
    document.querySelector('#login').onsubmit = () => {
      event.preventDefault();
      if (document.querySelector('#login-screen_name').value) {
        localStorage.setItem('screen_name', document.querySelector('#login-screen_name').value);
        screen_name = localStorage.getItem('screen_name');
        message_config();

        // Hide Login Form and Reveal Vote Buttons:
        document.querySelector('#login').style.display = "none";
        document.querySelector('#vote').style.display = "inline";
        }
      };

    // Check local storage for username, channel or subchannel if none, ask for a username:
    if (!localStorage.getItem('screen_name')) {
      document.querySelector('#login').style.display = "block";
      document.querySelector('#vote').style.display = "none";
      localStorage.setItem('channel', 'Home')
    } else {
      screen_name = localStorage.getItem('screen_name');

      if (!localStorage.getItem('channel')) {
        localStorage.setItem('channel', 'Home')
      }

      document.querySelector('#login').style.display = "none";
      message_config();
    }

    // Connect to the last saved channel or the home channel if none saved:
    socket.emit("join channel", {"channel": localStorage.getItem('channel'), "previous": localStorage.getItem('channel')});

    // When a new channel is joined, clear messages and display message history:
    socket.on('channel logon', data => {
      // Clear current messages
      document.querySelector('#votes').innerHTML = '';

      console.log('Getting message history...', data['message_history'])

      // Add all new messages:
      for (let i = 0; i < data['message_history'].length ; i++) {
        message = data['message_history'][i]

        // Create message li
        const li = document.createElement('li');
        li.innerHTML = `${message[1]}'s says: ${message[0]} - Posted ${message[3]} - `;

        // Create message date span
        const dateSpan = document.createElement('span');
        dateSpan.setAttribute('data-livestamp', message[2]);
        li.appendChild(dateSpan);

        // Add to messages element
        document.querySelector('#votes').append(li);
      }
    })

    // When a new vote is announced, add to the unordered list
    socket.on('announce vote', data => {
      console.log('Message broadcast received, message data:', data);

      // Create message li
      const li = document.createElement('li');
      li.innerHTML = `${data.message[1]}'s says: ${data.message[0]} - Posted ${data.message[3]} - `;

      // Create message date span
      const dateSpan = document.createElement('span');
      dateSpan.setAttribute('data-livestamp', data.message[2]);
      li.appendChild(dateSpan);

      // Add to messages element
      document.querySelector('#votes').append(li);

    });

    // When a new channel is added, update channel link buttons
    socket.on('channel added', data => {
      channel_config(data.channel_list);
    });
  });
});
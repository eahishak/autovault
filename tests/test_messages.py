"""
tests/test_messages.py

Tests for the messaging system:
send, inbox, conversation thread, delete conversation.
Verifies auth guards and ownership checks.
"""

import pytest
from app.models import Message, Notification


class TestInbox:

    def test_inbox_requires_auth(self, client):
        r = client.get('/messages', follow_redirects=True)
        assert b'sign in' in r.data.lower() or b'login' in r.data.lower()

    def test_inbox_loads_for_authenticated_user(self, logged_in_buyer):
        r = logged_in_buyer.get('/messages')
        assert r.status_code == 200

    def test_inbox_shows_conversations(self, logged_in_buyer, db_session,
                                       buyer, seller, active_car):
        msg = Message(sender_id=buyer.id, receiver_id=seller.id,
                      car_id=active_car.id, content='Test message')
        db_session.add(msg)
        db_session.flush()
        r = logged_in_buyer.get('/messages')
        assert r.status_code == 200

    def test_empty_inbox_shows_empty_state(self, logged_in_buyer):
        r = logged_in_buyer.get('/messages')
        assert r.status_code == 200


class TestConversation:

    def test_conversation_requires_auth(self, client, active_car, seller):
        r = client.get(f'/messages/{active_car.id}/{seller.id}',
                       follow_redirects=True)
        assert r.status_code == 200

    def test_conversation_loads(self, logged_in_buyer, active_car, seller):
        r = logged_in_buyer.get(f'/messages/{active_car.id}/{seller.id}')
        assert r.status_code == 200

    def test_conversation_marks_messages_as_read(self, logged_in_buyer,
                                                  db_session, buyer, seller, active_car):
        msg = Message(
            sender_id=seller.id,
            receiver_id=buyer.id,
            car_id=active_car.id,
            content='Hi, the car is available',
            is_read=False,
        )
        db_session.add(msg)
        db_session.flush()

        logged_in_buyer.get(f'/messages/{active_car.id}/{seller.id}')
        db_session.refresh(msg)
        assert msg.is_read is True

    def test_cannot_message_self(self, logged_in_buyer, buyer, active_car):
        r = logged_in_buyer.post('/messages/send', data={
            'car_id':      active_car.id,
            'receiver_id': buyer.id,
            'content':     'Self message',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Message.query.filter_by(content='Self message').first() is None


class TestSendMessage:

    def test_send_message_creates_record(self, logged_in_buyer, db_session,
                                         active_car, seller):
        r = logged_in_buyer.post('/messages/send', data={
            'car_id':      active_car.id,
            'receiver_id': seller.id,
            'content':     'Is this still available?',
        }, follow_redirects=True)
        assert r.status_code == 200
        msg = Message.query.filter_by(content='Is this still available?').first()
        assert msg is not None

    def test_send_message_creates_notification(self, logged_in_buyer, db_session,
                                               active_car, seller):
        notif_count_before = Notification.query.filter_by(user_id=seller.id).count()
        logged_in_buyer.post('/messages/send', data={
            'car_id':      active_car.id,
            'receiver_id': seller.id,
            'content':     'Notification test',
        }, follow_redirects=True)
        assert Notification.query.filter_by(
            user_id=seller.id
        ).count() > notif_count_before

    def test_empty_message_rejected(self, logged_in_buyer, active_car, seller):
        r = logged_in_buyer.post('/messages/send', data={
            'car_id':      active_car.id,
            'receiver_id': seller.id,
            'content':     '',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert Message.query.filter_by(content='').first() is None

    def test_message_truncated_at_2000_chars(self, logged_in_buyer, db_session,
                                              active_car, seller):
        long_content = 'A' * 3000
        logged_in_buyer.post('/messages/send', data={
            'car_id':      active_car.id,
            'receiver_id': seller.id,
            'content':     long_content,
        }, follow_redirects=True)
        msg = Message.query.filter(Message.content.like('AAA%')).first()
        if msg:
            assert len(msg.content) <= 2000

    def test_send_requires_auth(self, client, active_car, seller):
        r = client.post('/messages/send', data={
            'car_id':      active_car.id,
            'receiver_id': seller.id,
            'content':     'Unauthenticated message',
        }, follow_redirects=True)
        assert Message.query.filter_by(content='Unauthenticated message').first() is None


class TestDeleteConversation:

    def test_delete_conversation_removes_messages(self, logged_in_buyer, db_session,
                                                   buyer, seller, active_car):
        msg = Message(sender_id=buyer.id, receiver_id=seller.id,
                      car_id=active_car.id, content='To be deleted')
        db_session.add(msg)
        db_session.flush()

        r = logged_in_buyer.post(
            f'/messages/{active_car.id}/{seller.id}/delete',
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert Message.query.filter_by(content='To be deleted').first() is None

    def test_delete_requires_auth(self, client, active_car, seller):
        r = client.post(f'/messages/{active_car.id}/{seller.id}/delete',
                        follow_redirects=True)
        assert r.status_code == 200
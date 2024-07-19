from . import db

class PendingEmail(db.Model):
    __tablename__ = 'pending_email'
    nr_num = db.Column('nr_num', db.String(10), primary_key=True)
    decision = db.Column('decision', db.String(30))

    @classmethod
    def add_or_update_email(cls, nr_num, decision):
        print('\n\n\nADD OR UPDATE EMAIL')
        record = cls.query.filter_by(nr_num=nr_num).first()
        if record:
            print('UPDATING AN EXISTING RECORD\n')
            record.decision = decision
        else:
            print('CREATING A NEW RECORD\n')
            record = cls(nr_num=nr_num, decision=decision)
            db.session.add(record)
        db.session.commit()
    
    @classmethod
    def hold_email(cls, nr_num, decision):
        record = cls.query.filter_by(nr_num=nr_num).first()
        if record:
            print('UPDATING AN EXISTING RECORD\n')
            record.decision = decision

    @classmethod
    def get_decision(cls, nr_num):
        record = cls.query.filter_by(nr_num=nr_num).first()
        return record.decision if record else None

    @classmethod
    def delete_record(cls, nr_num):
        record = cls.query.filter_by(nr_num=nr_num).first()
        if record:
            db.session.delete(record)
            db.session.commit()

from . import db, state

class PendingEmail(db.Model):
    __tablename__ = 'pending_email'
    nr_num = db.Column('nr_num', db.String(10), primary_key=True)
    decision = db.Column('decision', db.String(30))

    @classmethod
    def add_or_update_email(cls, nr_num: str, decision: state):
        record = cls.query.filter_by(nr_num=nr_num).first()
        if record:
            record.decision = decision
        else:
            record = cls(nr_num=nr_num, decision=decision)
            db.session.add(record)
        db.session.commit()
    
    @classmethod
    def hold_email(cls, nr_num: str):
        record = cls.query.filter_by(nr_num=nr_num).first()
        if record:
            record.decision = state.HOLD

    @classmethod
    def get_decision(cls, nr_num: str):
        record = cls.query.filter_by(nr_num=nr_num).first()
        return record.decision if record else None

    @classmethod
    def delete_record(cls, nr_num: str):
        record = cls.query.filter_by(nr_num=nr_num).first()
        if record:
            db.session.delete(record)
            db.session.commit()

WHENEVER SQLERROR EXIT FAILURE ROLLBACK
CREATE TABLE type_category (
    type_name VARCHAR2(200 CHAR) NOT NULL,
    group_id NUMBER(2) NOT NULL,
    CONSTRAINT pk_type_category PRIMARY KEY (type_name, group_id),
    CONSTRAINT chk_type_category_group CHECK (group_id IN (2, 3, 4))
);
INSERT ALL
    INTO type_category VALUES ('кредит', 2)
    INTO type_category VALUES ('кредит', 3)
    INTO type_category VALUES ('Одобрение кредита', 2)
    INTO type_category VALUES ('Одобрение кредита', 3)
    INTO type_category VALUES ('обратный звонок/Заявка на кредит', 2)
    INTO type_category VALUES ('обратный звонок/Заявка на кредит', 3)
    INTO type_category VALUES ('обратный звонок/Кредит', 2)
    INTO type_category VALUES ('обратный звонок/Кредит', 3)
    INTO type_category VALUES ('приобретение автомобиля', 3)
    INTO type_category VALUES ('Плановое ТО', 4)
    INTO type_category VALUES ('Ремонт', 4)
    INTO type_category VALUES ('Диагностика', 4)
    INTO type_category VALUES ('Вопрос дилеру', 4)
    INTO type_category VALUES ('Другое', 4)
    INTO type_category VALUES ('обратный звонок/Автосервис', 4)
    INTO type_category VALUES ('Шиномонтаж', 4)
    INTO type_category VALUES ('Кузовной ремонт', 4)
    INTO type_category VALUES ('обратный звонок/Стоимость ТО', 4)
    INTO type_category VALUES ('Roadhelp', 4)
    INTO type_category VALUES ('обратный звонок/Продажа запасных частей и аксессуаров', 4)
SELECT 1 FROM dual;
COMMIT;
